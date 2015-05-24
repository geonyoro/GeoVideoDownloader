import requests
import os
import traceback
import logging
import time

downloader_instances = []

class Downloader(object):
	def __init__(self, output_filename, download_continue, url, user_agent="Mozilla/5.0 (Windows NT 5.2; rv:2.0.1) Gecko/20100101 Firefox/4.0.1"):
		global downloader_instances
		downloader_instances.append(self)

		url = url.rstrip("\n")

		self.output_filename = output_filename
		self.download_continue = download_continue
		self.url = url
		self.user_agent = user_agent
		self.completed = 0

		self.progress = 0
		self.progress_percent = 0
		self.total = 1024
		self.speed = 0

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
		if size:
			size-=1
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
				headers = {
					"user-agent": self.user_agent,
					"Range": "bytes=%s-" % action["size"]
				}

				self.progress+=action["size"]
				response = requests.get('%s'%self.url, headers=headers, stream=True, timeout=5)

				if 'content-range' in response.headers.keys():
					self.total = int(response.headers['content-range'].split("/")[1])

				if action["size"] == self.total:
					self.progress_percent = 100
					self.completed = 1
					continue

				w = open(self.output_filename, 'a')
				for chunk in response.iter_content(chunk_size=512*1024):
					self.speed = "{:.2f}".format( (len(chunk)/1024.0)/float(time.time()-previous_time) )
					previous_time = time.time()

					if not self.running:
						return
					self.progress += len(chunk)
					self.progress_percent = int(100*self.progress/float(self.total))
					w.write(chunk)
				w.close()

				self.running = 0
				self.progress_percent = 100
				self.completed = 1

			except requests.exceptions.ConnectionError:
				print "ConnectionError"
				pass
			except requests.exceptions.Timeout:
				print "timeout"
				pass
			except:
				self.error_message = "%s"%traceback.format_exc()
				print "Error\n%s"%self.error_message
				self.error_state = 1
				self.running = 0


if __name__=="__main__":
	d = Downloader("test_img.jpg", 1, "https://captbbrucato.files.wordpress.com/2011/08/dscf0585_stitch-besonhurst-2.jpg")