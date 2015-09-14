#! /usr/bin/env python

import requests
import os, sys
import traceback
import logging
import time
import socket
import ssl
import threading
import glob

config_dir = os.path.join(os.environ["HOME"], ".geon_downloader")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)

DIR = os.path.dirname(__file__)

logger = logging.getLogger('Background_Downloader')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler( os.path.join(config_dir, 'log.txt' ), mode='w')
# file_handler = logging.FileHandler( os.path.join(DIR, 'log2.txt' ), mode='w')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

downloader_instances = []
concurrent_downloads = 2

def humantime(new_time):
	output_string = ""
	for index, type_ in enumerate(["s", "m", "h"]):
		output_string = "%s%s"%( int(new_time%60), type_) + output_string
		if not int(new_time/60):
			break
		new_time = new_time/60
	return output_string

def humansize(nbytes):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    if nbytes == 0: return '0 B'
    i = 0
    while nbytes >= 1000 and i < len(suffixes)-1:
        nbytes /= 1000.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])

def file_rename(filename, segment_no=0 , get_part_path=0):
	if get_part_path:
		parent_dir, child_file = os.path.split(filename)
		filename = os.path.join(parent_dir, ".%s" % child_file)
		return filename + ".part.*"

	dirname = os.path.dirname(filename)
	file_ = os.path.split(filename)[1]
	filename = os.path.join( dirname, "." + str(file_) )
	return filename +".part.%s"%(segment_no)

class DownloadManager:
	def __init__(self, url, filename, continue_, segment_size, no_of_segments):
		if not url.startswith("http"):
			url = "http://"+url

		url = url.replace("\n", "")

		global downloader_instances
		downloader_instances.append(self)

		self.no_of_segments = no_of_segments
		self.continue_ = continue_
		self.filename = self.output_filename = filename
		self.url = url
		self.log_filename = os.path.split(self.filename)[-1]
		self.segment_size = segment_size

		headers = {
			"user-agent" : "Mozilla/5.0 (Windows NT 5.2; "+
				"rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
			"range": "bytes=0-"
			}

		connected = 0
		self.running = 1
		self.completed = 0
		self.pause = 0
		self.error = 0

		self.progress = 0
		if os.path.exists(self.filename) and self.continue_:
			self.progress = os.path.getsize(self.filename)
		self.percentage_written = 0
		self.speed = "-----"
		self.time_remaining_str = "--Querying--"

		self.corrector = 0.3

		self.finished_instances = self.running_instances = self.written = 0
		self.stats_lock = threading.Lock()

		# remove previous part files
		glob_path = file_rename(self.filename, get_part_path=1)
		for path in glob.glob(glob_path):
			try:
				parent_dir = os.path.split(glob_path)[0]
				os.remove(os.path.join(parent_dir, path))
			except Exception as e:
				print e

		while not connected and self.running:
			try:
				response = requests.get(url, headers=headers, 
					stream=True, timeout=10, verify=False)
				connected = 1
			except (requests.exceptions.Timeout, socket.timeout, 
				ssl.SSLError, requests.exceptions.ConnectionError):
				connected = 0
				traceback.print_exc()
				# logger.debug("Error on info obtaining  %s", 
					# self.output_filename)
				time.sleep(1)
			except:
				traceback.print_exc()

		if not self.running:
			self.time_remaining_str = "--Exiting--"
			return

		self.size = 0
		logger.debug("%s Status Code: %s", self.log_filename, response.status_code)
		print "Status Code %s" % response.status_code
		self.time_remaining_str = "--Waiting--"
		if response.status_code == 206:
			self.size = int(response.headers["content-length"])
			self.multiple_instances()
		elif response.status_code <= 226:
			self.size = int(response.headers["content-length"])
			self.single_instance()
		else:
			self.error = 1
			self.running = 0
			self.time_remaining_str = "--Error--"
			if response.status_code == 400:
				logger.info("Bad Request %s", os.path.split(self.filename)[-1] )
			elif response.status_code == 401:
				logger.info("Unauthorized %s", os.path.split(self.filename)[-1] )
			elif response.status_code == 403:
				logger.info("Forbidden %s", os.path.split(self.filename)[-1] )
			elif response.status_code == 404:
				logger.info("Not Found %s", os.path.split(self.filename)[-1] )
			elif response.status_code == 416:
				logger.info("Requested Range Not Satisfiable %s", os.path.split(self.filename)[-1] )
			else:
				logger.info("Status Code: %s", response.status_code)
			return

	def single_instance(self):
		t = threading.Thread(target = DownloadThread, kwargs={
					"url":self.url, 
					"filename":self.filename, 
					"start_position": self.get_start_stop_positions(), 
					"stop_position":self.size, 
					"segment_no":0,
					"manager":self
					})
		t.start()

	def set_waiting_string(self):
		self.time_remaining_str = "--Waiting--"

	def check_queue(self):
		"""Wait to ensure running instances do not exceed allowed number"""
		global concurrent_downloads
		while self.running:
			position_in_queue = downloader_instances.index(self)
			completed_download_items = 0
			for download_item in downloader_instances[:position_in_queue]:
				if download_item.completed:
					completed_download_items += 1
			if position_in_queue-completed_download_items < concurrent_downloads:
				break
			else:
				self.set_waiting_string()
			time.sleep(2)

		if not self.running:
			return "quit"

	def multiple_instances(self):
		segments = []
		stop = 0

		position_gen = self.get_start_stop_positions()
		speed_avg = 0
		start_size = 0
		self.progress_pool = {}
		self.time_remaining_str = "--Starting--"

		if os.path.exists(self.filename) and self.continue_:
			previous_progress = start_size = os.path.getsize(self.filename)
		else:
			previous_progress = 0
		previous_time = start_time = time.time()

		already_logged_that_app_is_paused = already_logged_that_app_is_paused_2 = 0

		#while loop for downloading
		while self.size > stop and self.running:
			if self.check_queue() == "quit":
				return

			if not already_logged_that_app_is_paused:
				already_logged_that_app_is_paused = 1
				logger.debug("%s paused", self.log_filename)

			if self.pause:
				while self.running_instances and self.running and self.pause:
					self.time_remaining_str = "Pausing %s" % self.running_instances
					time.sleep(0.5)

				self.speed = "-----"
				self.time_remaining_str = "Paused"
				time.sleep(0.5)
				continue

			#enqueue new threads
			while self.running_instances < self.no_of_segments and self.running:
				self.stats_lock.acquire(True)
				if self.pause:
					while self.running_instances and self.running:
						self.time_remaining_str = "Pausing %s" % self.running_instances
						time.sleep(0.5)

					self.speed = "-----"
					self.time_remaining_str = "Paused"
					time.sleep(0.5)
					continue
				try:
					positions = position_gen.next()
				except StopIteration:
					self.stats_lock.release()
					stop = self.size
					break

				start = positions["start"]	
				stop =  positions["stop"]
				t = threading.Thread(target = DownloadThread, kwargs={
					"url":self.url, 
					"filename":self.filename, 
					"start_position": start, 
					"stop_position":stop, 
					"segment_no":self.finished_instances+self.running_instances,
					"manager":self
					})
				t.start()
				self.running_instances += 1
				self.stats_lock.release()
			
			self.progress = 0
			if os.path.exists(self.filename):
				self.progress = os.path.getsize(self.filename)
			for i in self.progress_pool.itervalues():
					self.progress += i
			self.percentage_written = "{0:.2f}".format(float(self.progress) * 100/ self.size)

			if self.progress != previous_progress:
				delta_size = self.progress - start_size
				delta_time = time.time() - start_time
				speed = (delta_size / 1024.0) / delta_time
				factor = ( abs(speed_avg - speed) % 1000 ) / 1000
				if abs(speed_avg - speed) < 200:
					factor+=0.45
				# print "Speed: %s" % speed
				speed_avg = speed_avg*(1-factor)+ speed*factor
				# speed_avg = speed
				self.speed = "{0:.1f}".format( speed_avg )
				previous_progress = self.progress
				previous_time = time.time()
				time_r = humantime(((self.size-self.progress)/1024.0)/speed_avg)
				self.time_remaining_str = time_r
			time.sleep(1)

		while self.running:
			if os.path.exists(self.filename):
				if os.path.getsize(self.filename) >= self.size:
					break
			time.sleep(0.4)

		if not self.running:
			self.time_remaining_str = "--Exiting--"
			print "Exiting Manager"
			return	

		self.running = 0 
		self.completed = 1
		self.progress = os.path.getsize(self.filename)
		self.percentage_written = 100
		self.speed = "----"

	def get_start_stop_positions(self):
		initial_start = self.get_start()
		stop = 0
		count = 0

		while self.size > stop:
			start = self.segment_size*count + initial_start
			stop = start + self.segment_size - 1
			count += 1
			if start >= self.size:
				raise StopIteration()
			yield {
				"start": start, 
				"stop": stop
				}

	def get_start(self):	
		if self.continue_:
			if os.path.exists(self.filename):
				return os.path.getsize(self.filename)
		else:
			if os.path.exists(self.filename):
				os.remove(self.filename)
		return 0

class DownloadThread:
	def __init__(self, url, filename, start_position, stop_position, segment_no, manager):
		self.manager = manager
		self.url = url
		self.start_position = start_position
		self.stop_position = stop_position
		self.segment_no = segment_no
		self.log_filename = self.manager.log_filename

		self.progress = 0
		self.manager.progress_pool[self] = 0

		# print start_position, stop_position
		if start_position >= stop_position:
			self.manager.running_instances-= 1
			self.manager.finished_instances+=1
			self.manager.written += 1
			while self.segment_no > self.manager.written:
				time.sleep(1)
			print "Exiting %s" % segment_no
			return

		self.running = 1
		self.completed = 0

		parent, child = os.path.split(filename)
		self.output_filename = os.path.join(parent, ".%s.part.%s"%(child, segment_no) )

		self.run()

	def run(self):
		while self.running and not self.completed:
			try:
				headers = {
					"user-agent" : "Mozilla/5.0 (Windows NT 5.2; "+
						"rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
					"range": "bytes=%s-%s" %(self.start_position, self.stop_position)
					}
				response = requests.get(self.url, headers=headers, stream=True,  timeout=20, verify=False)
				# if "content-range" in response.headers.keys():
				# 	logger.debug("%s Segment %s Response: %s", self.log_filename, self.segment_no, response.headers["content-range"])
				
				logger.debug("%s Segment %s started", self.log_filename, self.segment_no)
				print "segment %s started" % self.segment_no
				with open(self.output_filename, 'w' ) as output_instance:
					for chunk in response.iter_content(chunk_size=80*1024):
						if not self.manager.running:
							logger.debug("%s Segment:%s Exiting", self.log_filename, self.segment_no)
							return
						output_instance.write(chunk)
						self.progress += len(chunk)
						self.manager.progress_pool[self] = self.progress
					self.running = 0 
					self.completed = 1

			except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,socket.timeout, ssl.SSLError):
				print "Error %s" % self.segment_no
				logger.debug("%s Minor Error", self.log_filename)
			except:
				logger.debug("%s Segment:%s Error: %s", self.log_filename, self.segment_no,traceback.format_exc() )
				traceback.print_exc()

		self.manager.stats_lock.acquire(True)
		self.manager.finished_instances += 1
		self.manager.running_instances -= 1
		self.manager.stats_lock.release()

		while self.segment_no > self.manager.written and self.manager.running:
			time.sleep(1)

		if not self.manager.running:
			return

		with open(self.manager.filename, 'a') as w:
			w2 = open(self.output_filename)
			content = w2.read()
			w.write(content)
			w2.close()
			del self.manager.progress_pool[self]

		logger.debug("%s Segment %s written", self.log_filename, self.segment_no)
		print "Segment %s written" % self.segment_no
		os.remove(self.output_filename)
		self.manager.written+=1

if __name__ == "__main__":
	pass
