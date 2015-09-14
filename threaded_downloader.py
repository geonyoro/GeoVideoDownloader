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

def file_rename(filename, segment_no=0 , get_glob=0):
	if get_glob:
		parent_dir, child_file = os.path.split(filename)
		filename = os.path.join(parent_dir, ".%s" % child_file)
		return filename + ".part.*"

	dirname = os.path.dirname(filename)
	file_ = os.path.split(filename)[1]
	filename = os.path.join( dirname, "." + str(file_) )
	return filename +".part.%s"%(segment_no)

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
		self.error = 0

		self.progress = 0
		self.percentage_written = 0
		self.speed = "-----"
		self.time_remaining_str = "--Querying--"

		self.downloaders = []

		self.corrector = 0.3

		headers = {
			"user-agent" : user_agent,
			"range": "bytes=0-"
			}
		connected = 0

		# get size of files already donwloaded
		if not self.download_continue:
			glob_path = file_rename(self.filename, get_glob=1)
			# logger.debug("glob path is %s", glob_path)
			removed_paths = "\n"
			for path in glob.glob(glob_path):
				removed_paths += "\t\t%s\n" % path
				try:
					os.remove(path)
				except:
					logger.error("Error removing path: %s", path)
		else:
			# download_continue
			for i in range(self.no_of_segments):
				child_filename = file_rename(self.filename, i)
				if os.path.exists(child_filename):
					self.progress += os.path.getsize(child_filename)

		# return

		while not connected and self.running:
			try:
				response = requests.get(url, headers=headers, stream=True, timeout=10, verify=False)
				connected = 1
			except (requests.exceptions.Timeout, socket.timeout, ssl.SSLError, requests.exceptions.ConnectionError):
				connected = 0
				logger.debug("Error on info obtaining  %s", self.output_filename)
				time.sleep(1)

		if not self.running:
			self.time_remaining_str = "--Exiting--"
			return

		self.size = 0
		self.time_remaining_str = "--Starting--"

		if response.status_code == 206:
			self.size = int(response.headers["content-length"])
			# print self.progress ,  float(self.size), self.progress / float(self.size)
			self.percentage_written = self.progress * 100 / self.size
			self.multiple_instances(self.size)
		elif response.status_code <= 226:
			logger.info("%s does not have resume capability or threads: Code %s", os.path.split(self.filename)[-1], response.status_code )
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


		time.sleep(1)
		self.manage()

	def single_instance(self):
		t = threading.Thread(target=DownloadThread, name="Single instance %s" % self.filename, kwargs={
			"filename" : self.filename,
			"url" : self.url,
			"user_agent" : self.user_agent,
			"start_pos" : 0,
			"end_pos" : self.size,
			"segment_no" : 1,
			"download_continue" : self.download_continue,
			"manager_instance" : self
		})
		t.start()

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

			t = threading.Thread(target=DownloadThread, name="%s %s" % (self.filename, i+1),kwargs={
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
		self.previous_progress = 0
		previous_time = 0
		self.speed_avg = 0
		while self.running and not self.completed:
			if self.pause:
				# wait until all threads paused before saying paused
				do_not_break = 1
				while do_not_break and self.running and
                                    self.pause:
					speed = 0
					instances_paused = 0
					do_not_break = 0
					for instance in self.downloaders:
						if instance.paused or instance.completed:
							instances_paused += 1
						else:
							try:
								speed += float(instance.speed)
							except Exception as e:
								pass
								# print e, repr( instance.speed )
							do_not_break = 1
					self.speed = "{0:.1f}".format(speed)
					if not do_not_break:
						break
					self.time_remaining_str = "Paused:%s/%s" % ( instances_paused, len(self.downloaders) )
					time.sleep(0.5)

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
				if instance.percentage_written!=0 and instance.speed!="" and not instance.completed:
					# print "--->", instance.segment_no, "P:",instance.percentage_written, "S:", instance.speed
					pass
			# count-=1
			changed_progress = progress - self.previous_progress
			#  we just started, assume we took 2 seconds to get this data
			if previous_time == 0:
				previous_time = time.time() - 2
			delta_time = time.time() - previous_time
			speed = (changed_progress/1024.0) / delta_time

			if all_completed:
				self.running = 0
				self.completed = 1

			try:
				# normally 0.3 for a difference of 100kbs
				# and 1 for a difference of 1mbps

				factor = ( abs(self.speed_avg - speed) % 1000 ) / 1000
				if abs(self.speed_avg - speed) < 200:
					factor+=0.1
				self.speed_avg = self.speed_avg*(1-factor)+ speed*factor
				time_r = humantime(((self.size-progress)/1024.0)/self.speed_avg)
				self.speed = "{:.1f}".format( self.speed_avg )
				previous_time = time.time()
				self.time_remaining_str = time_r
				self.previous_progress = progress

				if percentage/len(self.downloaders) > int(self.percentage_written):
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
			time.sleep(1.5)

		if not self.running and not self.completed:
			self.time_remaining_str = "--Exiting--"
			logger.info("Exiting Manager %s", self.output_filename)
			return

		self.percentage_written = 100
		self.speed ="---"
		self.time_remaining_str = "Joining Files"

		file_instance = open(self.filename, 'w')
		#these instances were added in order
		for instance in self.downloaders:
			if not instance.completed:
				logger.error("Problem with one of the downloads for %s", os.path.split(self.output_filename)[-1])
				break
			w = open(instance.output_filename)
			size = os.path.getsize(instance.output_filename)
			while 1:
				content = w.read(300000)
				file_instance.write(content)
				if size == w.tell():
					break
			try:
				# pass
				os.remove(instance.output_filename)
			except:
				logger.error("Unable to remove file: %s", instance.output_filename )
				logger.error( traceback.format_exc() )

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
		self.output_filename = file_rename(filename, segment_no)
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
		self.paused = 0

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
				logger.debug("\n\t\t\tFile:%s \n\t\t\tStart Pos:%s \n\t\t\tCovered:%s \n\t\t\tRequest Headers-Range:%s", os.path.split(self.output_filename)[-1], self.start_pos, size, headers["range"])

				if self.start_pos+size >= self.end_pos:
					self.completed = 1
					self.percentage_written = 100
					self.progress = os.path.getsize(self.output_filename)
					self.speed = "0"
					logger.debug("%s Finished", self.output_filename)
					return

				if self.manager_instance.pause:
					logger.info("Thread %s paused", os.path.split(self.output_filename)[1])
				while self.manager_instance.pause and self.running and self.manager_instance.running:
					self.paused = 1
					time.sleep(2)

				if not self.running:
					return

				response = requests.get(self.url, headers=headers, stream=True,  timeout=20, verify=False)

				if self.manager_instance.pause:
					logger.info("Thread %s paused", os.path.split(self.output_filename)[1])
				while self.manager_instance.pause and self.running and self.manager_instance.running:
					self.paused = 1
					time.sleep(2)

				if not self.running:
					return

				self.download_continue = 1
				if 'content-range' not in response.headers.keys():
					# logger.debug("Content Range not in headers: %s :%s", self.output_filename, response.status_code)
					# print "Problem with %s; %s" % (self.output_filename, headers["range"])
					# print response.headers["content-type"]
					# if content_range_retry_count > 1000:
					# 	self.running = 0
					# 	logger.info("Giving up on %s", self.output_filename)
					# 	return
					# else:
					# content_range_retry_count += 1
					# time.sleep(10)
					# continue
					content_range_retry_count += 1
					time.sleep(10)
					continue

				if response.status_code!=206:
					logger.debug("Bad response: %s File:%s Range:%s", response.status_code, os.path.split(self.output_filename)[-1], headers["range"])
					self.completed = 0
					continue

				# if "expires" in response.headers.keys():
				# 	logger.debug("%s \n\tExpires: %s \n\tContent-type:%s", os.path.split(self.output_filename)[-1], response.headers["expires"], response.headers["content-type"] )
				logger.debug("\n\t\t\tFilename: %s \n\t\t\tStatus:%s \n\t\t\tResponse Content-Range:%s \n\t\t\tContent-Type:%s", os.path.split(self.output_filename)[-1],  response.status_code,
					response.headers["content-range"], response.headers['content-type'])

				self.total = size + int(response.headers['content-length'])

				with open(self.output_filename, file_mode ) as output_instance:
					self.start_time = previous_time = time.time()
					paused_for_time = 0
					paused_at_time = 0
					for chunk in response.iter_content(chunk_size=50*1024):
						if not self.manager_instance.running or not self.running:
							logger.info("Exiting Thread %s" , self.output_filename)
							return

						if self.manager_instance.pause:
							self.paused = 1
							logger.info("Thread %s paused", os.path.split(self.output_filename)[1])
						while self.manager_instance.pause and self.running and self.manager_instance.running:
							paused_at_time = time.time()
							time.sleep(0.5)
							paused_for_time += (time.time() - paused_at_time)
							self.speed = 0
						if paused_for_time!=0:
							logger.info("Thread %s resumed", os.path.split(self.output_filename)[1])
							raise Exception("Resuming Thread")

						self.paused = 0
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
							self.running = 0
							logger.info("Exiting Thread %s" , self.output_filename)
							return

				self.progress = os.path.getsize(self.output_filename)
				self.completed = 1
				self.percentage_written = 100
				self.running = 0
				self.speed = "0"
				logger.debug("%s Finished", self.output_filename)
				return

			except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,socket.timeout, ssl.SSLError):
				logger.debug("Small Errors : %s", self.output_filename)
				time.sleep(1)
			except:
				# self.running = 0
				logger.error("%s %s", self.output_filename, traceback.format_exc() )

	def __str__(self):
		return "%s-%s" %(self.output_filename, self.url)

if __name__=="__main__":
	pass
