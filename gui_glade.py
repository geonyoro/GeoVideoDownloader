#!/usr/bin/env python
from gi.repository import Gtk, GdkPixbuf, GObject
import os
import time
import sys
import traceback
import threading
import logging
import datetime
import json

config_dir = os.path.join(os.environ["HOME"], ".geon_downloader")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)

logger = logging.getLogger('root')
logger.setLevel(logging.DEBUG)
logfile = os.path.join(config_dir, 'log_%s.txt' % (datetime.datetime.strftime(datetime.datetime.today(), "%Y-%m-%d")))
file_handler = logging.FileHandler(logfile, mode='a')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info("\n\n--Restarted Application--\n\n")

import threaded_downloader


DIR = os.path.dirname(os.path.abspath(__file__))
HOME_FOLDER = os.environ["HOME"]
default_path = HOME_FOLDER+os.path.sep+'Desktop'

config_file = os.path.join(os.path.join(HOME_FOLDER, ".geon_downloader"), "configs.json")

config = {
    "last_save_path" : HOME_FOLDER, 
    "segment_size" : threaded_downloader.segment_size,
    "segments_per_dl" : threaded_downloader.no_of_segments,
    "concurrent_downloads" : threaded_downloader.concurrent_downloads,
    "previous_files" : [],
}

if os.path.exists(config_file):
    with open(config_file) as w:
        try:
            config = json.loads(w.read())
        except:
            w.seek(0)
            logger.error("Unable to load json config from: %s", w.read())

exit_ = False
original_delete_event = None

def get_file_name(i):
    return os.path.split(i.filename)[1]

def save_config():
    global config
    try:
        with open(config_file, 'w') as w:
            w.write(json.dumps(config))
    except:
        logger.debug("Unable to write config to file:\n%s", traceback.format_exc())


def load_config():
    try:
        threaded_downloader.segment_size = config["segment_size"] * 1024
    except:
        with open(config_file) as w:
            logger.error("Error loading Segments Size from [Config File:%s]\n[Error:%s]", w.read(), traceback.format_exc())

    try:
        threaded_downloader.concurrent_downloads = config["concurrent_downloads"]
    except:
        with open(config_file) as w:
            logger.error("Error loading Concurrent Downloads from [Config File:%s]\n[Error:%s]", w.read(), traceback.format_exc())

    try:
        threaded_downloader.no_of_segments = config["segments_per_dl"]
    except:
        with open(config_file) as w:
            logger.error("Error loading No Of Segments from [Config File:%s]\n[Error:%s]", w.read(), traceback.format_exc())

    if "previous_files" not in config.keys():
        config["previous_files"] = []


if "last_save_path" in config.keys():
    default_path = config["last_save_path"]

load_config()

class App:
    def __init__(self):
        global config, DIR

        self.builder = builder = Gtk.Builder()
        glade_file = os.path.join(DIR, "glade"+os.path.sep+"gui.glade")
        builder.add_from_file(glade_file)
        builder.connect_signals(self)

        self.build()

        self.window_main = window = builder.get_object("window_main")
        window.set_icon_from_file(os.path.join(DIR , "res" + os.path.sep + "icon1.jpeg" ))
        window.show_all()

        self.tv1.columns_autosize()
        selection = self.tv1.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        # x = 0
        # self.add_new_download(output_filename="/home/george/Desktop/test.mp4", url="http://127.0.0.1/SampleVideo_1280x720_1mb.mp4", erase=x)
        # self.add_new_download(output_filename="/home/george/Desktop/test1.mp4", url="http://127.0.0.1/SampleVideo_1280x720_1mb.mp4", erase=x)
        # self.add_new_download(output_filename="/home/george/Desktop/test2.mp4", url="http://127.0.0.1/SampleVideo_1280x720_1mb.mp4", erase=x)

        for downloadable in config["previous_files"]:
            self.add_new_download(output_filename=downloadable["filename"], url=downloadable["url"], erase=False, allow_error_dialog=False)
            pass

        self.run_timeout_id = GObject.timeout_add(100, self.run)

    def run(self):
        global exit_ 
        self.tv_model1 = self.tv1.get_model()
        if not self.tv_model1:
            self.tv_model1 = Gtk.ListStore(str, str, str, str, str, str, str)
            self.tv1.set_model(self.tv_model1)

        top_iter = self.tv_model1.get_iter_first()
        iter_ = top_iter

        all_files = []


        def get_icon(i):
            icon = Gtk.STOCK_APPLY if i.completed else Gtk.STOCK_MEDIA_PLAY
            icon = Gtk.STOCK_MEDIA_PAUSE if (i.pause and not i.completed) else icon
            icon = Gtk.STOCK_DIALOG_ERROR if i.error else icon
            return icon

        def add_new_row(i):
            self.tv_model1.append([get_file_name(i), i.url, str(threaded_downloader.humansize(i.progress)), str(i.percentage_written), str(i.speed), i.time_remaining_str, get_icon(i)])

        total_speed = 0
        for i in threaded_downloader.download_manager_instances:
            found_row_for_i = False
            try:
                total_speed += float(i.speed)
            except:
                pass

            for row in self.tv_model1:
                if row[0] == get_file_name(i):
                    # update the details for the row
                    found_row_for_i = True
                    for index, item in enumerate([get_file_name(i), i.url, str(threaded_downloader.humansize(i.progress)), str(i.percentage_written), str(i.speed), i.time_remaining_str, get_icon(i)]):
                        row[index] = item
                    break

            if not found_row_for_i:
                add_new_row(i)
            
        self.builder.get_object("label_speed").set_markup("Approximate Total Speed: <b>%s</b> kbps" % total_speed)

        if exit_:
            self.window_main.emit("delete-event", original_delete_event)


        return True

    def build(self):
        self.tv1 = self.builder.get_object("treeview1")

        for i in [
                {"colname": "Filename", "model-column":0, "fixed_width": 150, "max_width": 150, "can-expand":False},
                {"colname": "URL", "model-column":1, "fixed_width":290, "max_width": 400, "can-expand":False},
                {"colname": "Progress", "model-column":2, "fixed_width": 80, "max_width": 90, "can-expand":False},
                {"colname": "Percent", "model-column":3, "fixed_width": 80, "max_width":90, "can-expand":False},
                {"colname": "Speed", "model-column":4, "fixed_width": 80, "max_width": 90, "can-expand":False},
                {"colname": "Time Remaining", "model-column":5, "fixed_width": 120, "max_width": 130, "can-expand":False},
                {"colname": "Time Remaining", "model-column":5, "fixed_width": 20, "max_width": 30, "can-expand":False, "type":"pix"},
        ]:
            if i.has_key("type"):
                renderer_pixbuf = Gtk.CellRendererPixbuf()
                column_pixbuf = Gtk.TreeViewColumn("Status", renderer_pixbuf, stock_id=6)
                self.tv1.append_column(column_pixbuf)
                continue

            self.tvcolumn = Gtk.TreeViewColumn(i["colname"])
            self.tvcolumn.set_expand(i["can-expand"])
            self.tvcolumn.set_fixed_width(i["fixed_width"])
            self.tvcolumn.set_max_width(i["max_width"])

            # self.tvcolumn.set_sizing(Gtk.TREE_VIEW_COLUMN_FIXED)
            self.tvcolumn.set_resizable(True)
            self.tv1.append_column(self.tvcolumn)
            self.cell = Gtk.CellRendererText()
            self.cell.set_padding(5, 4)
            self.tvcolumn.pack_start(self.cell, True)
            self.tvcolumn.add_attribute(self.cell, 'text', i["model-column"])

        self.tv1.set_tooltip_column(1,)

        self.set_defaults()

    def save_session(self):
        global config

        previous_files = []
        for i in threaded_downloader.download_manager_instances:
            if not i.completed:
                previous_files.append({
                    "filename" : i.filename,
                    "url" : i.url,
                })

        config["previous_files"] = previous_files

    def set_defaults(self):
        self.builder.get_object("entry_segment_size").set_text(str(config["segment_size"]))
        self.builder.get_object("entry_segments_per_dl").set_text(str(config["segments_per_dl"]))
        self.builder.get_object("entry_concurrent_downloads").set_text(str(config["concurrent_downloads"]))

    def on_window1_delete_event(self, window, event):
        global exit_, original_delete_event
        original_delete_event = event

        if not exit_:
            # First time in this block
            logger.info("Waiting for %s Download Manager(s) to close.", len(threaded_downloader.download_manager_instances))
            exit_ = True
            
            for inst in threaded_downloader.download_manager_instances:
                logger.debug("Killing Manager of %s", os.path.split(inst.filename)[1])
                inst.running = False

        if threading.active_count() > 1:
            return True

        self.save_session()
        save_config()
        self.window_main.destroy()
        return False

    def on_window1_destroy(self, event, data=None):
        Gtk.main_quit()

    def on_btn_clear_completed_downloads_clicked(self, event, data=None):
        for index, i in enumerate(threaded_downloader.download_manager_instances):
            if i.completed:
                for row in self.tv_model1:
                    if row[0] == get_file_name(i):
                        self.tv_model1.remove(row.iter)
                        break

                del threaded_downloader.download_manager_instances[index]

    def on_btn_save_session_clicked(self, event, data=None):
        self.save_session() 

    def on_btn_suspend_clicked(self, event, data=None):
        print 5

    def on_btn_select_all_clicked(self, event, data=None):
        selection = self.tv1.get_selection()
        model, pathlist = selection.get_selected_rows()

        # by default, prefer choosing everything
        if len(pathlist) == len([row for row in self.tv1.get_model()]):
            selection.unselect_all()
        else:
            selection.select_all()

    def on_btn_choose_output_filename_clicked(self, event, data=None):
        print 7

    def on_btn_add_download_clicked(self, event, data=None):
        win_add_dl = self.builder.get_object("window_add_download")

        self.builder.get_object("entry_outfilename").set_text("")
        url_buffer = self.builder.get_object("textview_url").get_buffer()
        url_buffer.set_text("")

        win_add_dl.show_all()

    def on_btn_remove_clicked(self, event, data=None):
        restart = True
        filenames_to_remove = []

        while restart:
            selection = self.tv1.get_selection()
            model, pathlist = selection.get_selected_rows()
            restart = False

            for path in pathlist:
                row = model[path]
                filenames_to_remove.append(row[0])
                model.remove(row.iter)
                restart = True
                break

        for filename in filenames_to_remove:
            for index, instance in enumerate(threaded_downloader.download_manager_instances):
                if get_file_name(instance) == filename:
                    del threaded_downloader.download_manager_instances[index]

    def on_btn_pause_clicked(self, event, data=None):
        selection = self.tv1.get_selection()
        model, pathlist = selection.get_selected_rows()
        if pathlist != None:
            for path in pathlist:
                filename = model[path][0]
                for i in threaded_downloader.download_manager_instances:
                    if filename == get_file_name(i):
                        # toggle pause
                        i.pause = not i.pause
                        break



    def on_entry_segments_per_dl_focus_out_event(self, event, data=None):
        global config
        no_of_segments = self.builder.get_object("entry_segments_per_dl").get_text()
        try:
            threaded_downloader.no_of_segments = int(no_of_segments)
            config["segments_per_dl"] = int(no_of_segments)
        except:
            self.show_dialog("Invalid No Of Segments set.")

        return False

    def on_entry_segment_size_focus_out_event(self, event, data=None):
        segment_size = self.builder.get_object("entry_segment_size").get_text()
        try:
            threaded_downloader.segment_size = int(segment_size) * 1024
            config["segment_size"] = int(segment_size)
        except:
            self.show_dialog("Invalid Segment Size set.")

        return False

    def on_entry_concurrent_downloads_focus_out_event(self, event, data=None):
        concurrent_downloads = self.builder.get_object("entry_concurrent_downloads").get_text()
        try:
            threaded_downloader.concurrent_downloads= int(concurrent_downloads)
            config["concurrent_downloads"] = int(concurrent_downloads)
        except:
            self.show_dialog("Invalid No of Concurrent Downloads set.")

        return False

    def on_btn_add_downloa_clicked(self, event, data=None):
        global config

        win_add_dl = self.builder.get_object("window_add_download")
        output_filename = self.builder.get_object("entry_outfilename").get_text()

        if output_filename.strip(" ") == "" :
            self.show_dialog("Set Filename Please!")
            return

        url_buffer = self.builder.get_object("textview_url").get_buffer()
        url  = url_buffer.get_text(url_buffer.get_start_iter(), url_buffer.get_end_iter(), True).replace("\n", "").strip(" ")

        if url == "" :
            self.show_dialog("Set Url Please!")
            return

        erase = self.builder.get_object("cb_erase").get_active()
        config["last_save_path"] = os.path.dirname(os.path.abspath(output_filename))
        self.add_new_download(output_filename, url, erase)
        win_add_dl.hide()

    def on_btn_cancel_download_clicked(self, event, data=None):
        win_add_dl = self.builder.get_object("window_add_download")
        win_add_dl.hide()

    def show_dialog(self, message, title="Error", type_="error"):
        my_types = {
            "error":  Gtk.MessageType.ERROR,
            "info":  Gtk.MessageType.INFO,
            "warning":  Gtk.MessageType.WARNING,
            "question":  Gtk.MessageType.QUESTION,
        }
        
        my_buttons = {
            "error":  Gtk.ButtonsType.CANCEL,
            "info":  Gtk.ButtonsType.OK,
            "warning":  Gtk.ButtonsType.OK_CANCEL,
            "question":  Gtk.ButtonsType.YES_NO
        }

        dialog = Gtk.MessageDialog(self.window_main, 0, my_types[type_], my_buttons[type_], title)
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def on_window_add_download_delete_event(self, event, data=None):
        win_add_dl = self.builder.get_object("window_add_download")
        win_add_dl.hide()
        return True

    def on_btn_choose_output_clicked(self, event, data=None):
        file_buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
    	dialog = Gtk.FileChooserDialog(title="Choose Output Filename", parent=self.builder.get_object("window_main"), buttons=file_buttons, action=Gtk.FileChooserAction.SAVE)
        dialog.set_current_folder(default_path)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
            self.builder.get_object("entry_outfilename").set_text(filename)

        dialog.destroy()

    def add_new_download(self, output_filename, url, erase, allow_error_dialog=True):
        "Starts a thread for new download. Does not allow duplicates"

        output_filename = output_filename.strip(" ")
        url = url.strip(" ")
        for i in threaded_downloader.download_manager_instances:
            if i.url == url and i.output_filename == output_filename:
                if allow_error_dialog:
                    self.show_dialog("Duplicate Item detected!")
                return

        threading.Thread(target = threaded_downloader.DownloadManager, args=[url, output_filename, not erase]).start()

    def on_treeview1_cursor_changed(self, event, data=None):
    	print 3

    def on_treeview1_focus_out_event(self, event, data=None):
        selection = self.tv1.get_selection()
        # selection.unselect_all()

    def on_btn_open_file_loc_clicked(self, event, data=None):
        selection = self.tv1.get_selection()
        model, pathlist = selection.get_selected_rows()
        if pathlist != None:
            for path in pathlist:
                path = pathlist[0]
                filename = model[path][0]
                for instance in threaded_downloader.download_manager_instances:
                    if get_file_name(instance) == filename:
                        os.system("xdg-open '%s'" % os.path.dirname(os.path.abspath(instance.filename)))
                        break

    # def (self, event, data=None):
    # 	print 3

    # def (self, event, data=None):
    # 	print 3



if __name__ == "__main__":
    app = App()
    try:
        Gtk.main()
    except:
        logger.error("Major Error: Exiting:\n%s", traceback.format_exc())
        for i in threaded_downloader.download_manager_instances:
            i.running = False
        sys.exit(-1)
    logger.info("Quitting application")
