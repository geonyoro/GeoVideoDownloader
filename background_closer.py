#!/usr/bin/env python2
import os, datetime, sys, time, threading
if os.getuid() != 0:
	print "Not Root"
	sys.exit(1)
dirname = os.path.dirname(__file__)
running = 1 
# running = 0
lock_updater_running = 0

lock_path = os.path.join(dirname, ".lock")
try:
	if os.path.exists(lock_path):
		content = ""
		with open(lock_path) as w:
			content = w.read()
		if len(content):
			hour, minute, second = [ int(i) for i in content.split(":") ]
			time_delta = datetime.datetime.now() - datetime.datetime.now().replace(hour=hour, minute=minute, second=second)
			if time_delta.total_seconds() < 10:
				# there is another background_closer running
				print "Another Instance is running"
				sys.exit(0)
except Exception as e:
	print 5*str(e)
	sys.exit(2)

def lock_updater():
	global running, lock_updater_running
	lock_updater_running = 1
	while running:
			try:
				x = datetime.datetime.now()
				x.time()
				time_string = datetime.time.strftime(x.time(), "%H:%M:%S")
				w = open(lock_path,'w')
				w.write(time_string)
				w.close()
				time.sleep(5)
			except Exception as e:
				print 5*str(e)
				sys.exit(2)

	try:
		w = open(lock_path, 'w')		
		w.write(time_string)
		w.write("")
		w.close()
		lock_updater_running = 0
		return
	except Exception as e:
		print 5*str(e)
		sys.exit(1)

threading.Thread(target = lock_updater).start()
check_file = os.path.join(dirname, ".check")
while 1:
	if os.path.exists(check_file):
		# print "Exists"
		try:
			os.remove(check_file)
			running = 0 
			while lock_updater_running:
				print "waiting for lock updater"
				time.sleep(1)
			os.system("pm-suspend")
		except:
			running = 0
		break
	else:
		time.sleep(2)

# print "Exiting"