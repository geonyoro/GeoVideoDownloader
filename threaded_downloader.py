#! /usr/bin/env python

import requests
import os, sys
import traceback
import logging
import time
import socket
import ssl
import threading

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

# headers = {
# 		"user-agent" : "Mozilla/5.0 (Windows NT 5.2; rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
# 		"range": "bytes=120538239-180807357"
# 		}
# response = requests.get("http://stor29.streamcloud.eu:8080/4pv74wxkn6oax3ptx3jyjr7gup2aedcvce2ilivygda5thzw5mr4h7tvze/video.mp4", headers=headers, stream=True)
# print response.status_code, response.headers

downloader_instances = []

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
    while nbytes >= 1024 and i < len(suffixes)-1:
        nbytes /= 1024.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])

class DownloadManager(object):
	def __init__(self, filename, download_continue, url, user_agent, no_of_segments=1):
		global downloader_instances
		if not url.startswith("http"):
			url = "http://"+url

		downloader_instances.append(self)

		url = str(url.rstrip("\n"))
		user_agent = str(user_agent.rstrip("\n"))

		self.url = url
		self.download_continue = download_continue
		self.filename = self.output_filename = filename
		self.user_agent = user_agent
		self.no_of_segments = no_of_segments

		self.running = 1
		self.completed = 0
		self.pause = False

		self.progress = 0
		self.percentage_written = 0
		self.speed = "0"
		self.time_remaining_str = "----"

		self.downloaders = []

		self.corrector = 0.3

		headers = {
			"user-agent" : user_agent,
			"range": "bytes=0-"
			}
		connected = 0
		while not connected and self.running:
			try:
				response = requests.get(url, headers=headers, stream=True, timeout=20, verify=False)
				connected = 1
			except (requests.exceptions.Timeout, socket.timeout, ssl.SSLError, requests.exceptions.ConnectionError):
				logger.debug("Error on info obtaining  %s", self.output_filename)
				time.sleep(1)


		logger.debug("Status_Code: %s \tfilename:%s", response.status_code, self.filename)
		self.size = 0
		if response.status_code!=206:
			logger.debug("Item does not have resume capability or threads")
			self.single_instance()
		else:
			self.size = int(response.headers["content-length"])
			self.multiple_instances(self.size)

		time.sleep(1)
		self.manage()

	def single_instance(self):
		pass

	def multiple_instances(self, size):
		start = 0
		for i in range(self.no_of_segments):
			end_pos = start+size/self.no_of_segments
			if i == self.no_of_segments-1:
				end_pos = size

			if i!=0:
				start_pos = start+1
			else:
				start_pos = 0

			t = threading.Thread(target=DownloadThread, kwargs={
				"filename" : self.filename, 
				"url" : self.url, 
				"user_agent" : self.user_agent, 
				"start_pos" : start_pos, 
				"end_pos" : end_pos, 
				"segment_no" : i+1,
				"download_continue" : self.download_continue,
				"manager_instance" : self
			})

			t.start()
			start += (size/self.no_of_segments)
			time.sleep(0.5)
			# print start

	def manage(self):
		while self.running and not self.completed:
			if self.pause:
				self.speed = "-----"
				self.time_remaining_str = "Paused"
				time.sleep(0.5)
				continue

			percentage = 0
			speed = 0
			progress = 0
			all_completed = 1
			for instance in self.downloaders:
				if not instance.running and not instance.completed:
					print "Problem", instance.output_filename
				if instance.completed:
					print "Finished", instance.output_filename
				else:
					all_completed = 0 
				percentage += instance.percentage_written
				progress += instance.progress
				try:
					speed += float(instance.speed)
				except:
					pass
				if instance.percentage_written!=0 and instance.speed!="" and not instance.completed:
					print "--->", instance.segment_no, "P:",instance.percentage_written, "S:", instance.speed
					pass
			# count-=1
			if all_completed:
				self.running = 0
				self.completed = 1

			try:
				time_r = humantime(((self.size-progress)/1024.0)/speed)
				self.time_remaining_str = time_r
				self.speed = self.speed = "{:.1f}".format( speed )
				self.percentage_written = percentage/len(self.downloaders)
				self.progress = progress
				# print "To go: %s" % (humansize(self.size-progress))
				progress_string = ">Progress: %s \tCovered:%s/%s \tTo Go:%s \t Speed:%s \tTime:%s" % (self.percentage_written, 
					humansize(progress), humansize(self.size), humansize(self.size-progress), speed,  time_r)
				# logger.debug(progress_string)
				print progress_string,"\n"
				sys.stdout.flush()
			except ZeroDivisionError:
				pass
			except:
				logger.error(traceback.format_exc())
			# print count
			time.sleep(1)

		if not self.running and not self.completed:
			logger.info("Exiting Manager %s", self.output_filename)
			return 

		file_instance = open(self.filename, 'w')
		for instance in self.downloaders:
			w = open(instance.output_filename)
			size = os.path.getsize(instance.output_filename)
			while 1:
				content = w.read(100000)
				file_instance.write(content)
				if size == w.tell():
					break
			try:
				os.remove(instance.output_filename)
			except:
				pass

		if not self.running and not self.completed:
			logger.debug("Problem with download" % self.output_filename)
			return

		self.running = 0
		self.completed = 1
		self.speed ="---"
		self.time_remaining_str = "---"
		self.percentage_written = 100

class DownloadThread(object):
	def __init__(self, filename, url, download_continue, user_agent, start_pos, end_pos, segment_no, manager_instance):
		dirname = os.path.dirname(filename)
		file_ = os.path.split(filename)[1]
		self.filename = os.path.join( dirname, "." + str(file_) )
		self.output_filename = self.filename +".part.%s"%(segment_no)
		self.user_agent = user_agent
		self.segment_no = segment_no
		self.manager_instance = manager_instance
		self.download_continue = download_continue

		self.manager_instance.downloaders.append(self)
		# print self.output_filename, "S", start_pos, "E", end_pos
		self.url = url
		self.start_pos = start_pos
		self.end_pos = end_pos
		self.total = 0

		self.running = 1
		self.completed = 0

		self.size_written = 0
		self.percentage_written = 0
		self.progress = 0
		self.speed = ""
		self.speed_avg = 0

		self.download()

	def download(self):
		while self.running and self.manager_instance.running and not self.completed:			
			try:
				if self.download_continue:
					if os.path.exists(self.output_filename):
						size = os.path.getsize(self.output_filename)
						file_mode = "a"
					else:
						size = 0
						file_mode = "w"

					self.progress = int(size)
				else:
					self.progress = 0
					file_mode = "w"
					size = 0 

				content_range_retry_count = 0

				headers = {
					"user-agent" : self.user_agent,
					"range": "bytes=%s-%s" %(self.start_pos+size, self.end_pos)
					}
				logger.debug("Headers: %s %s",headers, self.output_filename)

				if self.start_pos+size >= self.end_pos:
					self.completed = 1
					self.percentage_written = 100
					self.progress = os.path.getsize(self.output_filename)
					self.speed = "0"
					logger.debug("%s Finished", self.output_filename)
					return

				response = requests.get(self.url, headers=headers, stream=True,  timeout=20, verify=False)
				self.download_continue = 1
				if 'content-range' not in response.headers.keys():
					logger.debug("Content Range not in headers: %s :%s", self.output_filename, response.status_code)
					# print "Problem with %s; %s" % (self.output_filename, headers["range"])
					# print response.headers["content-type"]
					if content_range_retry_count > 1000:
						self.running = 0
						logger.info("Giving up on %s", self.output_filename)
						return
					else:
						content_range_retry_count += 1
						time.sleep(5)
						continue

				if response.status_code!=206:
					logger.debug("Bad response: %s File:%s Range:%s", response.status_code, self.output_filename, headers["range"])
					self.completed = 0
					continue

				if "expires" in response.headers.keys():
					logger.debug("%s \n\tExpires: %s \n\tContent-type:%s", self.output_filename, response.headers["expires"], response.headers["content-type"] )
				logger.debug("Filename: %s Seg: %s Status:%s %s %s", self.output_filename, self.segment_no, response.status_code, 
					response.headers["content-range"], response.headers['content-type'])

				self.total = size + int(response.headers['content-length'])

				with open(self.output_filename, file_mode ) as output_instance:
					self.start_time = previous_time = time.time()
					paused_for_time = 0
					paused_at_time = 0
					for chunk in response.iter_content(chunk_size=50*1024):
						while self.manager_instance.pause and self.running and self.manager_instance.running:
							paused_at_time = time.time()
							time.sleep(0.5)
							paused_for_time += (time.time() - paused_at_time)

						time_taken = time.time() - previous_time - paused_for_time
						paused_for_time = 0

						new_speed = (len(chunk)/1024.0)/float(time_taken)
						if abs(new_speed - self.speed_avg) < 1000:
							self.speed_avg = new_speed*self.manager_instance.corrector + self.speed_avg * (1-self.manager_instance.corrector)
						self.speed = "{:.1f}".format( self.speed_avg )
						previous_time = time.time()

						self.progress += len(chunk)
						self.percentage_written = int(100*self.progress/float(self.total))
						output_instance.write(chunk)	

						if not self.manager_instance.running or not self.running:
							logger.info("Exiting Thread %s" , self.output_filename)
							return

				self.progress = os.path.getsize(self.output_filename)
				self.completed = 1
				self.percentage_written = 100
				self.running = 0
				self.speed = "0"
				logger.debug("%s Finished", self.output_filename)
			except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,socket.timeout, ssl.SSLError):
				logger.debug("Small Errors : %s", self.output_filename)
				time.sleep(1)
			except:
				# self.running = 0
				logger.debug("%s %s", self.output_filename, traceback.format_exc() )

	def __str__(self):
		return "%s-%s" %(self.output_filename, self.url)

if __name__=="__main__":
	pass