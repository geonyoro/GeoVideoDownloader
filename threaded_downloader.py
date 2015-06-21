#! /usr/bin/env python

import requests
import os
import traceback
import logging
import time
import socket
import ssl
import threading


DIR = os.path.dirname(__file__)

logger = logging.getLogger('Background_Downloader')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler( os.path.join(DIR, 'log2.txt' ), mode='w')
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

		self.progress = 0
		self.progress_percent = 0
		self.speed = "0"
		self.time_remaining_str = "----"

		self.downloaders = []

		self.corrector = 0.3

		headers = {
			"user-agent" : user_agent,
			"range": "bytes=0-"
			}
		connected = 0
		while not connected:
			try:
				response = requests.get(url, headers=headers, stream=True, timeout=20)
				connected = 1
			except (requests.exceptions.Timeout, socket.timeout, ssl.SSLError, requests.exceptions.ConnectionError):
				logger.debug("Error on info obtaining")


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

			# print start_pos,"-",end_pos

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
				if instance.percentage_written!=0 and instance.speed!="":
					print "--->", instance.segment_no, "P:",instance.percentage_written, "S:", instance.speed
			# count-=1
			if all_completed:
				self.running = 0
				self.completed = 1

			try:
				time_r = humantime(((self.size-progress)/1024.0)/speed)
				self.time_remaining_str = time_r
				self.speed = self.speed = "{:.1f}".format( speed )
				self.progress_percent = percentage/len(self.downloaders)
				self.progress = progress
				# print "To go: %s" % (humansize(self.size-progress))
				progress_string = ">Progress: %s \tCovered:%s/%s \tTo Go:%s \t Speed:%s \tTime:%s" % (self.progress_percent, humansize(progress), humansize(self.size), humansize(self.size-progress), speed,  time_r)
				# logger.debug(progress_string)
				print progress_string,"\n"
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

		if not self.running and not self.completed:
			logger.debug
			return

		self.running = 0
		self.completed = 1
		self.speed ="---"
		self.time_remaining_str = "---"

class DownloadThread(object):
	def __init__(self, filename, url, download_continue, user_agent, start_pos, end_pos, segment_no, manager_instance):
		self.filename = filename
		self.output_filename = filename +".part.%s"%(segment_no)
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

		headers = {
			"user-agent" : self.user_agent,
			"range": "bytes=%s-%s" %(self.start_pos+size, self.end_pos)
			}

		content_range_retry_count = 0
		while self.running and self.manager_instance.running and not self.completed:
			try:
				response = requests.get(self.url, headers=headers, stream=True,  timeout=20)
				
				if 'content-range' not in response.headers.keys():
					logger.debug("Content Range not in headers")
					print "Problem with %s; %s" % (self.output_filename, headers["range"])
					# print response.headers["content-type"]
					if content_range_retry_count > 2:
						self.running = 0
						return
					else:
						content_range_retry_count += 1
						time.sleep(2)
						continue

				logger.debug("Filename: %s Seg: %s Status:%s %s %s", self.output_filename, self.segment_no, response.status_code, response.headers["content-range"], response.headers['content-type'])

				self.total = size + int(response.headers['content-length'])

				output_instance = open(self.output_filename, file_mode )

				self.start_time = previous_time = time.time()
				for chunk in response.iter_content(chunk_size=150*1024):
					time_taken = time.time()-previous_time
					new_speed = (len(chunk)/1024.0)/float(time_taken)
					if abs(new_speed - self.speed_avg) < 1000:
						self.speed_avg = new_speed*self.manager_instance.corrector + self.speed_avg * (1-self.manager_instance.corrector)
					self.speed = "{:.1f}".format( self.speed_avg )
					previous_time = time.time()

					if not self.manager_instance.running or not self.running:
						logger.info("Exiting Thread %s" , self.output_filename)
						return

					self.progress += len(chunk)
					self.percentage_written = int(100*self.progress/float(self.total))
					output_instance.write(chunk)

				self.completed = 1
				self.percentage_written = 100
				self.running = 0
				logger.debug("%s Finished", self.output_filename)
			except requests.exceptions.ConnectionError:
				self.speed = "--CE--"

	def __str__(self):
		return "%s-%s" %(self.output_filename, self.url)

if __name__=="__main__":
	DownloadManager(
		filename ="24-9-2.flv", 
		download_continue = 1,
		url="http://s213.mighycdndelivery.com/dl/9f59add83cb2a51acb2b4f235a00b77c/5586763a/ff010597194d1bc9458015ab0ad1f9636e.flv?client=FLASH",
		user_agent="Mozilla/5.0 (Windows NT 5.2; rv:2.0.1) Gecko/20100101 Firefox/4.0.1", 
		no_of_segments=8)
	# DownloadManager(filename = "test2.mp4", 
	# 	url = "https://r4---sn-f5o5ojip-ocve.googlevideo.com/videoplayback?key=yt5&mime=video%2Fmp4&itag=18&id=o-AMkqcs827bCUtM3IJVzbKD6cBogSyLaShwSTnFEhQAs7&signature=217E1993986D9F038D868AFF9C0488F0DB4AF70F.F021162487C69ED7A7A60AECD75B8DDDD936BBBF&ms=au&mv=m&upn=XhNnEjF59Nk&mt=1434878905&expire=1434900542&pl=22&mn=sn-f5o5ojip-ocve&ip=197.237.60.150&mm=31&requiressl=yes&initcwndbps=778750&source=youtube&ipbits=0&lmt=1434387396974357&sparams=dur%2Cid%2Cinitcwndbps%2Cip%2Cipbits%2Citag%2Clmt%2Cmime%2Cmm%2Cmn%2Cms%2Cmv%2Cpl%2Cratebypass%2Crequiressl%2Csource%2Cupn%2Cexpire&fexp=936117%2C9406990%2C9407141%2C9408142%2C9408420%2C9408710%2C9413503%2C9414764%2C9415304%2C9416126%2C9416456%2C952640&dur=90.697&ratebypass=yes&sver=3",
	# 	user_agent = "Mozilla/5.0 (Windows NT 5.2; rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
	# 	no_of_segments = 8)
# https://r4---sn-f5o5ojip-ocve.googlevideo.com/videoplayback?key=yt5&mime=video%2Fmp4&itag=18&id=o-AMkqcs827bCUtM3IJVzbKD6cBogSyLaShwSTnFEhQAs7&signature=217E1993986D9F038D868AFF9C0488F0DB4AF70F.F021162487C69ED7A7A60AECD75B8DDDD936BBBF&ms=au&mv=m&upn=XhNnEjF59Nk&mt=1434878905&expire=1434900542&pl=22&mn=sn-f5o5ojip-ocve&ip=197.237.60.150&mm=31&requiressl=yes&initcwndbps=778750&source=youtube&ipbits=0&lmt=1434387396974357&sparams=dur%2Cid%2Cinitcwndbps%2Cip%2Cipbits%2Citag%2Clmt%2Cmime%2Cmm%2Cmn%2Cms%2Cmv%2Cpl%2Cratebypass%2Crequiressl%2Csource%2Cupn%2Cexpire&fexp=936117%2C9406990%2C9407141%2C9408142%2C9408420%2C9408710%2C9413503%2C9414764%2C9415304%2C9416126%2C9416456%2C952640&dur=90.697&ratebypass=yes&sver=3