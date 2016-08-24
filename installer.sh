#! /bin/bash
if [ `id -u` -ne 0 ]; then
    	echo "Not root, exiting";
	exit;
fi
appname=geodownloadmanager
echo /usr/local/bin/$appname
cp ../$appname /usr/local/bin -r
chown $LOGNAME /usr/local/bin/$appname -R
chmod go+r /usr/local/bin/$appname -R
chmod +x /usr/local/bin/$appname
cp ./$appname.desktop /home/george/.local/share/applications/
chmod +x ./$appname.desktop
