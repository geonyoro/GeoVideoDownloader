#! /usr/bin/env python
import random

import requests
import os, sys
import traceback
import logging
import time
import socket
import ssl
import threading
import glob
import datetime
import tempfile

config_dir = os.path.join(os.environ["HOME"], ".geon_downloader")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)

DIR = os.path.dirname(__file__)

logger = logging.getLogger('root.Background_Downloader')

download_manager_instances = []
concurrent_downloads = 2
segment_size = 300 * 1024
no_of_segments = 5

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
    if nbytes == 0:
        return '0 B'

    i = 0
    while nbytes >= 1000 and i < len(suffixes)-1:
        nbytes /= 1000.
        i += 1

    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])

class DownloadManager:
    def __init__(self, url, filename, continue_, ):
        global download_manager_instances, segment_size, no_of_segments


        if not url.startswith("http"):
            url = "http://"+url

        url = url.replace("\n", "").strip(" ")

        download_manager_instances.append(self)

        self.no_of_segments = no_of_segments
        self.continue_ = continue_
        self.filename = self.output_filename = filename
        self.url = url
        self.log_filename = os.path.split(self.filename)[-1]

        self.start_byte_for_thread = self.get_start()
        self.end_byte_for_thread = self.start_byte_for_thread + segment_size 

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
        self.time_remaining_str = "-- Querying --"

        self.corrector = 0.3

        self.finished_instances = self.running_instances = self.written = 0
        self.stats_lock = threading.Lock()

        while not connected and self.running:
            try:
                response = requests.get(url, headers=headers,
                                        stream=True, timeout=10, verify=False)
                connected = 1
            except (requests.exceptions.Timeout, socket.timeout, 
                    ssl.SSLError, requests.exceptions.ConnectionError):
                connected = 0
                logger.debug("Error found while obtaining info on %s: %s",
                             self.output_filename, traceback.format_exc())
                time.sleep(1)
            except:
                traceback.print_exc()
                logger.error("Error Found: %s", traceback.format_exc())
                sys.exit(1)

        if not self.running:
            self.time_remaining_str = "-- Exiting --"
            return

        self.completed_file_size = 0
        logger.debug("File: %s Status Code: %s", self.log_filename, response.status_code)
        self.time_remaining_str = "-- Waiting --"

        self.speed_avg = 0
        self.start_size = 0
        self.progress_pool = {}
        self.started_at_time = time.time() 
        self.paused_time = 0
        self.already_logged_that_app_is_paused  = 0

        if response.status_code == 206:
            self.completed_file_size = self.get_content_length(response.headers)
            if self.completed_file_size:
                self.multiple_instances()
            else:
                self.single_instance(unknown_file_size = True)
        elif response.status_code == 200:
            self.completed_file_size = self.get_content_length(response.headers)
            self.single_instance()
        else:
            self.error = 1
            self.running = 0
            self.time_remaining_str = "-- Error --"
            if response.status_code == 400:
                logger.error("Bad Request %s", os.path.split(self.filename)[-1] )
            elif response.status_code == 401:
                logger.error("Unauthorized %s", os.path.split(self.filename)[-1] )
            elif response.status_code == 403:
                logger.error("Forbidden %s", os.path.split(self.filename)[-1] )
            elif response.status_code == 404:
                logger.error("Not Found %s", os.path.split(self.filename)[-1] )
            elif response.status_code == 416:
                logger.error("Requested Range Not Satisfiable %s", os.path.split(self.filename)[-1] )
            else:
                logger.error("Status Code: %s", response.status_code)
            return

    def get_content_length(self, response_headers):
        if "content-length" in response_headers.keys():
            return int(response_headers["content-length"])
        
        if "content-range" in response_headers.keys():
            full_size = response_headers["content-range"]
            if len(full_size.split("/")) == 2:
                return int(full_size.split("/")[1])

        # we don't have a statistic to do this kind of download, run single instances
        return None

    def single_instance(self, unknown_file_size = False):
        t = threading.Thread(target = DownloadThread, kwargs={
            "url" : self.url, 
            "filename" : self.filename, 
            "start_position" :  self.get_start(), 
            "stop_position" : "unknown" if unknown_file_size else self.completed_file_size, 
            "segment_no" : 0,
            "manager" : self
        })
        t.start()

    def set_waiting_string(self):
        self.time_remaining_str = "-- Waiting --"

    def check_queue(self):
        """Wait to ensure running instances do not exceed allowed number"""
        global concurrent_downloads

        while self.running:
            position_in_queue = download_manager_instances.index(self)
            completed_download_items = 0
            for download_item in download_manager_instances[:position_in_queue]:
                if download_item.completed:
                    completed_download_items += 1
            if position_in_queue-completed_download_items < concurrent_downloads:
                break
            else:
                self.set_waiting_string()
            time.sleep(0.5)

        if not self.running:
            return "quit"

    def manage_downloads(self):
        global no_of_segments, segment_size

        t = time.time()
        if self.check_queue() == "quit":
            return

        
        # wait for all threads to pause then show string
        if self.pause:
            if not self.already_logged_that_app_is_paused:
                self.already_logged_that_app_is_paused = 1
                logger.debug("%s paused", self.log_filename)

            while self.running_instances and self.running and self.pause:
                self.time_remaining_str = "Pausing %s" % self.running_instances
                time.sleep(0.5)

            self.speed = "-----"
            self.time_remaining_str = "Paused"
            time.sleep(0.5)

        if not self.pause:
            self.already_logged_that_app_is_paused = False

        #paused, reset time waiting
        self.paused_time += (time.time() - t)

        #enqueue new threads
        while self.running_instances < no_of_segments and self.running and not self.pause:
            if self.start_byte_for_thread > self.completed_file_size:
                break

            self.stats_lock.acquire(True)

            end_byte = self.start_byte_for_thread + segment_size - 1 

            t = threading.Thread(target = DownloadThread, kwargs={
                "url" : self.url, 
                "filename" : self.filename, 
                "start_position" : self.start_byte_for_thread, 
                "stop_position" : end_byte if (end_byte <= self.completed_file_size) else self.completed_file_size,
                "segment_no" : self.finished_instances + self.running_instances,
                "manager" : self
            })
            t.start()
            self.running_instances += 1

            self.end_byte_for_thread = self.start_byte_for_thread + segment_size
            self.start_byte_for_thread = self.end_byte_for_thread

            self.stats_lock.release()
            time.sleep(0.1)


        self.progress = 0

        if os.path.exists(self.filename):
            self.progress = os.path.getsize(self.filename)

        for i in self.progress_pool.itervalues():
            self.progress += i

        self.percentage_written = "{0:.2f}".format(float(self.progress) * 100 / self.completed_file_size)

        if self.progress != self.previous_progress:
            delta_size = self.progress - self.start_size
            delta_time = time.time() - self.started_at_time - self.paused_time
            speed = (delta_size / 1024.0) / delta_time
            factor = ( abs(self.speed_avg - speed) % 1000 ) / 1000

            if abs(self.speed_avg - speed) < 200:
                factor += 0.45

            self.speed_avg = self.speed_avg * (1 - factor) + speed * factor
            self.speed = "{0:.1f}".format( self.speed_avg )
            self.previous_progress = self.progress
            time_r = humantime(((self.completed_file_size - self.progress) / 1024.0) / self.speed_avg)
            self.time_remaining_str = time_r

        time.sleep(0.2)

    def multiple_instances(self):
        self.time_remaining_str = "-- Starting --"

        if os.path.exists(self.filename) and self.continue_:
            self.previous_progress = self.start_size = os.path.getsize(self.filename)
        else:
            self.previous_progress = 0


        self.manage_downloads()

        cx = 0   

        #while loop for downloading
        while self.running:
            try:
                self.manage_downloads()

                cx = (cx + 1) % 10

                if os.path.exists(self.filename):
                    file_size = os.path.getsize(self.filename)
                    if cx / 10:
                        logger.debug("[File: %s] FileSize: %s CompletedSize: %s EndByte: %s" % (self.filename, file_size, self.completed_file_size, self.end_byte_for_thread))
                        pass

                    if file_size == self.completed_file_size:
                        logger.info("Finished Downloading File %s", self.filename)
                        break
                    elif file_size > self.completed_file_size:
                        logger.warning("Download for [File: %s] has exceeded maximum size!", self.log_filename)
                        break

            except:
                logger.error("Error managing downloads for %s:\n%s", self.filename, traceback.format_exc())

            time.sleep(1)

        if not self.running:
            self.time_remaining_str = "--Exiting--"
            logger.debug("Exiting Manager for [File: %s]", self.log_filename)
            return	

        self.running = 0 
        self.completed = 1
        self.error = 0
        self.progress = os.path.getsize(self.filename)
        self.percentage_written = 100
        self.time_remaining_str = "--- Done ---"
        self.speed = "----"

        logger.debug("Exiting Manager for [File: %s]", self.log_filename)
  
    def get_start(self):	
        if self.continue_:
            if os.path.exists(self.filename):
                logger.debug("Starting Download for [File: %s] at [Pos: %s]", self.filename, os.path.getsize(self.filename))
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

        # time.sleep(random.randint(1,5)) # for simulating slow down
        if stop_position != "unknown": 
            if start_position >= stop_position:
                self.manager.running_instances-= 1
                self.manager.finished_instances+=1
                self.manager.written += 1
                while self.segment_no > self.manager.written:
                    time.sleep(1)
                
                if start_position > stop_position:
                    logger.debug("Exiting Thread for [File: %s]  [Segment No : %s] [Start Position: \
                                 '%s'] is larger than [Stop_position: '%s']", self.log_filename,
                                 segment_no, start_position, stop_position)
                return

        else:
            self.stop_position = ""

        self.running = 1
        self.completed = 0

        try:
            self.output_filename = tempfile.mkstemp(suffix=".segment", prefix="geon_downloader")[1]
        except:
            logger.error("Unable to create tempfile: %s", traceback.format_exc())

        self.run()

    def run(self):
        logger.debug("Starting download thread of [File: '%s'] [Segment: '%s'] [Start Pos: '%s'] [Stop Pos: '%s']", self.log_filename, self.segment_no, self.start_position, self.stop_position)

        while self.running and not self.completed and self.manager.running:
            try:
                headers = {
                    "user-agent" : "Mozilla/5.0 (Windows NT 5.2; "+
                    "rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
                    "range": "bytes=%s-%s" %(self.start_position, self.stop_position)
                }
                response = requests.get(self.url, headers=headers, stream=True,  timeout=20, verify=False)
                # logger.debug("[File : %s] Segment No: [%s] Headers: %s" , self.log_filename, self.segment_no, response.headers)
                self.progress = 0

                with open(self.output_filename, 'w' ) as output_instance:
                    for chunk in response.iter_content(chunk_size=80*1024):
                        if not self.manager.running:
                            logger.debug("[File: '%s'] Segment: '%s' exiting.", self.log_filename, self.segment_no)
                            return
                        output_instance.write(chunk)
                        self.progress += len(chunk)
                        # logger.debug("[File: '%s'] Segment: '%s' Progress: %s", self.log_filename, self.segment_no, self.progress/1024)
                        self.manager.progress_pool[self] = self.progress

                    self.running = 0 
                    self.completed = 1

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,socket.timeout, ssl.SSLError):
                logger.debug("Timeout error on %s", self.log_filename)
            except requests.models.ChunkedEncodingError:
                logger.debug("Incomplete read on [File: %s] [Segment: %s]. Restarting read.", self.log_filename, self.segment_no)
            except:
                logger.error("[File: %s] [Segment: %s] Error:\n %s", self.log_filename, self.segment_no,traceback.format_exc() )
                break

        if not self.manager.running:
            logger.debug("[File: '%s'] Segment: '%s' exiting.", self.log_filename, self.segment_no)
            return

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

        logger.debug("[File: %s] [Segment: %s] written.", self.log_filename, self.segment_no)
        try:
            os.remove(self.output_filename)
        except:
            logger.error("Unable to remove file: %s", self.output_filename)

        self.manager.written+=1

if __name__ == "__main__":
    pass
    # DownloadManager(filename="/home/george/Desktop/test.mp4", url="http://www.sample-videos.com/video/mp4/720/big_buck_bunny_720p_2mb.mp4", continue_=not True)
