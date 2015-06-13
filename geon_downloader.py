import requests
import os
import traceback
import logging
import time
import socket
import ssl

DIR = os.path.dirname(__file__)

config_dir = os.path.join(os.environ["HOME"], ".geon_downloader")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)

logger = logging.getLogger('Background_Downloader')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler( os.path.join(config_dir, 'log.txt' ), mode='w')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

downloader_instances = []
def humansize(nbytes):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    if nbytes == 0: return '0 B'
    i = 0
    while nbytes >= 1024 and i < len(suffixes)-1:
        nbytes /= 1024.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])

class Downloader(object):
	def __init__(self, output_filename, download_continue, url, user_agent="Mozilla/5.0 (Windows NT 5.2; rv:2.0.1) Gecko/20100101 Firefox/4.0.1"):
		global downloader_instances

		if not url.startswith("http"):
			logger.warning("Appending http:// to url %s", url)
			url = "http://" + url
		downloader_instances.append(self)

		url = str(url.rstrip("\n"))
		user_agent = str(user_agent.rstrip("\n"))

		self.output_filename = output_filename
		self.download_continue = download_continue
		self.url = url
		self.user_agent = user_agent
		self.completed = 0
		self.time_remaining = 0
		self.time_remaining_str = 0

		self.speed_avg = 0

		self.corrector = 0.2

		self.progress = 0
		self.progress_percent = 0
		self.total = 1024
		self.speed = 0

		self.start_time = 0

		self.error_state = 0
		self.error_message = ""

		self.running = 1

		self.run()

	def check_if_continue_or_start(self):
		if not os.path.exists(self.output_filename):
			return {
				"type": "start",
				"size": 0
				}

		#path exists
		if not self.download_continue:
			os.remove(self.output_filename)
			return {
				"type": "start",
				"size": 0
				}

		size = os.path.getsize(self.output_filename)
		# if size!=0:
		# 	size-=1
		return {
			"type" : "continue",
			"size" : size
		}

	def run(self):
		self.running = 1
		self.error_message = ""
		self.error_state = 0

		previous_time = time.time()

		while self.running and not self.completed:
			try:
				action = self.check_if_continue_or_start()
				logger.debug("Starting Action: output_filename: %s : %s", os.path.split(self.output_filename)[-1], action["type"] )
				headers = {
					"user-agent": self.user_agent,
					"Range": "bytes=%s-" % action["size"]
				}
				file_mode = 'a'

				self.progress = action["size"]
				logger.debug("Starting Progress: output_filename: %s : %s", os.path.split(self.output_filename)[-1], humansize(self.progress ) )

				response = requests.get('%s'%self.url, headers=headers, stream=True, timeout=20, verify=False)

				logger.debug("status: %s", response.status_code)
				headers_string = ""
				for k,v in response.headers.iteritems():
					headers_string += "%s:%s"%(k,v)
				logger.debug("Filename: %s\n\t\tResponse headers: %s", self.output_filename, headers_string )

				if 'content-range' in response.headers.keys():
					self.total = int(response.headers['content-range'].split("/")[1])

				else:
					file_mode = 'w'
					action['size'] = 0
					self.progress = 0
					self.progress_percent = 0

				if action["size"] == self.total:
					self.progress_percent = 100
					self.completed = 1
					logger.debug("Progress: output_filename: %s : Total Reached", os.path.split(self.output_filename)[-1] )
					continue


				w = open(self.output_filename, file_mode )

				self.start_time = time.time()
				for chunk in response.iter_content(chunk_size=100*1024):
					new_speed = (len(chunk)/1024.0)/float(time.time()-previous_time)
					self.speed_avg = new_speed*0.3 + self.speed_avg * 0.7
					self.speed = "{:.1f}".format( self.speed_avg )
					previous_time = time.time()
					logger.debug("Writing chunk: %s : output_filename: %s: new_speed: %s: average_speed: %s : chunk_size: %s : time_taken: %s", humansize(self.progress), os.path.split(self.output_filename)[-1], new_speed, self.speed, len(chunk), time.time()-previous_time) 

					if not self.running:
						return
					self.progress += len(chunk)
					self.progress_percent = int(100*self.progress/float(self.total))
					w.write(chunk)

					#time_remaining area
					download_size_remaining = self.total - self.progress
					try:
						self.time_remaining = (download_size_remaining/1024.0)/float(self.speed)
					except:
						logger.error(traceback.format_exc())
					self.update_time_remaining_str()

				w.close()

				self.time_remaining_str = "---"
				self.running = 0
				self.progress_percent = 100
				self.completed = 1
				logger.info("Finished: output_filename: %s finished downloading", os.path.split(self.output_filename)[-1] )
				self.speed = "++C++"

			except requests.exceptions.ConnectionError:
				# print "ConnectionError"
				self.speed = "--CE--"
				action = self.check_if_continue_or_start()
				logger.debug("CE: Action: %s, Progress: %s", action, humansize(self.progress) )
				self.time_remaining_str = "---"

			except (requests.exceptions.Timeout,socket.timeout, ssl.SSLError):
				# print "timeout"
				self.speed = "--TO--"
				action = self.check_if_continue_or_start()
				self.progress = action["size"]	
				logger.debug("TO/SSl: Action: %s, Progress: %s", action, humansize(self.progress) )
				self.time_remaining_str = "---"

			except:
				self.error_message = "%s" % traceback.format_exc()
				# print "Error\n%s"%self.error_message
				self.error_state = 1
				self.running = 0
				logger.debug("other Error: Action: %s \n\t\t%s", action, self.error_message)


	def update_time_remaining_str(self):
		new_time = self.time_remaining
		output_string = ""
		for index, type_ in enumerate(["s", "m", "h"]):
			output_string = "%s%s"%( int(new_time%60), type_) + output_string
			if not int(new_time/60):
				break
			# output_string = ":" + output_string
			new_time = new_time/60
		# print self.time_remaining, new_time, output_string
		self.time_remaining_str = output_string



if __name__=="__main__":
	pass
	# d = Downloader("/home/george/Desktop/test_img.jpg", 1, "https://captbbrucato.files.wordpress.com/2011/08/dscf0585_stitch-besonhurst-2.jpg")