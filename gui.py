#! /usr/bin/env python
import Tkinter as Tk
import ttk
import tkFont
import tkMessageBox
import tkFileDialog
import threading
import traceback
import logging
import requests
import os
import time
import sys

DIR = os.path.dirname(__file__)

import threaded_video_downloader

logger_main = logging.getLogger('GUI')
logger_main.setLevel(logging.DEBUG)
logger_main.addHandler(threaded_video_downloader.file_handler)
exit_app = threading.Event()

on_completion_touch_file = os.path.join(DIR, ".check")

want_to_exit = 0
shown_message_want_to_exit = 0

downloads_grid_row = 1

# colors
mouse_over_download_color = "#BBBBBB"
mouse_clicked_on_download_color = "#00D9A8"
download_default_color = "#E6E6E6"
download_error_color = "#FF5050"
download_completed_color = "#27B4FF"
entry_background_color = "#0D4D4D"
textcolor = "#669999"
textcolor = "#7AA6A6"
color2="#407F7F"
app_background = "#003333"
button_background = textcolor
highlightcolor=color2

#config directory
config_dir = os.path.join(os.environ["HOME"], ".geon_downloader")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)

class App(Tk.Frame):
    background_gray_1 = app_background
    def __init__(self):
        Tk.Frame.__init__(self, bg=App.background_gray_1)
        self.suspend_on_quit = 0
        self.current_mouse_over_download = 0
        self.current_mouse_clicked_on_download = 0
        self.session_resumed = 0

        self.update_interval = 50

        self.output_filename = None

        # sys.exit(1)

        # self.master.wm_iconbitmap("@geondownloader.xbm")

        self.dialog_initial_directory = os.path.join(os.environ["HOME"],"Videos")

        self.bigFont = tkFont.Font(root=self.master, size=12, underline=1)
        self.progressFont=tkFont.Font(root=self.master, size=9)
        self.downloadsFont=tkFont.Font(root=self.master, size=8, underline=0)
        
        self.master.columnconfigure(0, weight=1, minsize=500)
        self.master.rowconfigure(0, weight=1)

        self.master.title("GeoN Download Manager")
        self.master.geometry("{0}x{1}+100+0".format(840,670))
        self.widgets={}

        # resizing
        self.columnconfigure(0, weight=1)
        # self.columnconfigure(1, weight=1)
        self.basic_widgets()

        self.grid(row=0,column=0, sticky="nsew")
        self.master.protocol("WM_DELETE_WINDOW", lambda: self.onquit(button_press=1) ) 

        self.after( self.update_interval, self.update_window)   
        self.resume_session()
        self.update_idletasks()
        self.master.minsize(650, self.winfo_height())

        self.widgets["e_num_downloads"].my_widget.bind("<FocusOut>", lambda x:self.set_no_of_concurrent_downloads() )

    def set_no_of_concurrent_downloads(self):
        number = threaded_video_downloader.concurrent_downloads
        try:
            number = int(self.widgets["e_num_downloads"].get())
            logger_main.debug("Set Number of downlaods to %s", number)
        except:
            logger_main.debug(traceback.format_exc())

        threaded_video_downloader.concurrent_downloads = number

    def onquit(self, button_press = 0):
        global exit_app, want_to_exit, shown_message_want_to_exit

        self.clear_completed()
        self.save_session(no_prompt=1)

        for i in threaded_video_downloader.downloader_instances:
            i.running = 0
            
        if button_press:
            shown_message_want_to_exit = 0

        if len( threading.enumerate() ) > 1 :
            if not shown_message_want_to_exit:
                logger_main.info("Showing message for exit.")
                logger_main.debug("Running Threads: %s", threading.enumerate() )

                win = Tk.Toplevel(bg="#f8f8f8")
                # win.lift()
                l = Tk.Label(win, bg="#f8f8f8", text = "Closing all background Downloaders...\nWill exit the app after finished.").grid(padx=20)
                win.title("Exiting")
                win.update_idletasks()
                master_dimensions, master_x, master_y = self.master.winfo_geometry().split("+")
                master_width, master_height = master_dimensions.split("x")

                my_dim, my_x, my_y = win.winfo_geometry().split("+")
                my_width, my_height = my_dim.split('x')

                my_x = int(master_x) + int(master_width)/2 - int(my_width)/2
                my_y = int(master_y) + int(master_height)/2 - int(my_height)/2

                win.geometry("x".join([str(my_width), str(my_height)])+"+"+"+".join([str(my_x), str(my_y)]),)

                win.update_idletasks()
                win.attributes("-topmost",1)
                win.overrideredirect(1)
                
                win.transient(self.master)
                
                shown_message_want_to_exit = 1

            want_to_exit = 1
        else:
            exit_app.set()
            self.master.destroy()
            self.master.quit()

    def basic_widgets(self):           
        # button_grid
            bg = Tk.Frame(self, bg=App.background_gray_1)
            for i in [
                # {"widget_name": "btn_start", "row": 0, "column": 0, "text": "Start",   "command": self.start_downloads },
                {"widget_name": "btn_clear_completed", "row": 0, "column": 1, "text": "Clear Completed Downloads", "command": self.clear_completed },
                {"widget_name": "btn_save_session", "row": 0, "column": 2, "text": "Save Session", "command": self.save_session },
                {"widget_name": "btn_suspend", "row": 0, "column": 3, "text": "Suspend on Finish", "command": self.start_on_completion_script },
                {"widget_name": "btn_pause_session", "row": 0, "column": 4, "text": "Pause/Resume All", "command": self.pause_resume_all_downloads },
            ]:
                b = Tk.Button(bg, text=i["text"], command=i["command"], bg=button_background, relief="flat")
                self.widgets[i["widget_name"]] = b
                b.grid(row=0, column=i["column"], sticky="", padx=5, pady=2)

            bg.grid(row=0,column=0)

        # input_grid
            ig = Tk.Frame(self, bg=App.background_gray_1)
            widths = 70
            for i in range(2):
                bg.columnconfigure(i, weight=1)
            for i in [
                # {"type": "label", "widget_name": "", "row": 1, "column": 0, "text": "Output Filename:",  },
                {"type": "label", "widget_name": "", "row": 2, "column": 0, "text": "Continue:" },
                {"type": "label", "widget_name": "", "row": 3, "column": 0, "text": "URL:" },
                {"type": "label", "widget_name": "", "row": 4, "column": 0, "text": "# of Segments Per Download:" },
                {"type": "label", "widget_name": "", "row": 5, "column": 0, "text": "# of Concurrent Downloads:" },
                {"type": "label", "widget_name": "", "row": 6, "column": 0, "text": "Segment Size in kB:" },

                {"type": "button", "widget_name": "", "columnspan": 1, "row": 1, "ipadx": 0, "column": 0, "columnspan": 2, "text": "Choose Output Filename", "command": self.choose_output},

                # {"type": "listb", "row": 3, "column": 1, "widget_name": "listb_url", "text":
                #     "https://captbbrucato.files.wordpress.com/2011/08/dscf0585_stitch-besonhurst-2.jpg" },
                {"type": "listb", "row": 3, "column": 1, "widget_name": "listb_url", "text":
                    "" },

                {"type": "checkb", "row": 2, "column": 1, "default_state": 0, "widget_name": "cb_continue" },
                
                {"type": "entry", "row": 4, "column": 1, "default_state": 0, "text":5, "width":10, "widget_name": "e_num_segments" },
                {"type": "entry", "row": 5, "column": 1, "default_state": 0, "text":"3", "width":10, "widget_name": "e_num_downloads" },
                {"type": "entry", "row": 6, "column": 1, "default_state": 0, "text":"300", "width":10, "widget_name": "e_segment_size" },

                {"type": "button", "widget_name": "btn_add", "row": 8, "column": 0, "ipadx": 60, "columnspan": 2, "text": "Add", "command": self.add_download },
                
                {"type": "separat", "row": 7, "column": 0, "columnspan": 2 },
                {"type": "separat", "row": 0, "column": 0, "columnspan": 2 }
            ]:
                if i["type"] == "label":
                    w = Tk.Label(ig, text=i["text"], fg="white", bg=App.background_gray_1)
                    w.grid(row=i["row"], column=i["column"], sticky="e")

                elif i["type"] == "entry": 
                    var = Tk.StringVar()
                    var.set(i["text"])
                    self.widgets[i["widget_name"]] = var
                    w = Tk.Entry(ig, bg=entry_background_color, fg="white", highlightbackground=highlightcolor, width=widths, textvariable=var, relief="flat")
                    if i.has_key("width"):
                        w.config(width=i["width"])
                    var.my_widget = w
                    w.grid(row=i["row"], column=i["column"], sticky="w", padx=8, pady=5, ipadx=3)

                elif i["type"] == "checkb":
                    var = Tk.IntVar()
                    var.set(i["default_state"])
                    self.widgets[i["widget_name"]] = var
                    w = Tk.Checkbutton(ig, highlightbackground=highlightcolor, bg=App.background_gray_1, variable=var)
                    w.grid(row=i["row"], column=i["column"], sticky="w", padx=8, pady=5)

                elif i["type"] == "listb":
                    w = Tk.Text(ig, fg="white", bg=entry_background_color, highlightbackground=highlightcolor, height=2, width=widths, relief="flat")
                    self.widgets[i["widget_name"]] = w
                    w.insert('0.0', i['text'] )
                    w.grid(row=i["row"], column=i["column"], sticky="ew", padx=8, pady=5)

                elif i["type"] == "button":
                    b = Tk.Button(ig, text=i["text"], command=i["command"], bg=button_background, relief="flat")
                    self.widgets[i["widget_name"]] = b
                    b.grid(row=i["row"], column=i["column"], columnspan=i["columnspan"], sticky="", padx=5, ipadx=i["ipadx"])

                elif i["type"] == "separat":
                    s = ttk.Style()
                    s.configure('Sep.TSeparator', foreground=entry_background_color)
                    s.configure('Sep.TSeparator', background=entry_background_color)
                    s.configure('Sep.TSeparator', highlightbackground=entry_background_color)
                    sep = ttk.Separator(ig, orient=Tk.HORIZONTAL ,style='Sep.TSeparator')
                    pass
                    # foreground='maroon')
                    sep.grid(row=i["row"], column=i["column"], columnspan=i["columnspan"], sticky="ew", padx=5, pady=10)    

            ig.grid(row=1,column=0)

        # downloads_grid
            dg = Tk.Frame(self,bg=App.background_gray_1, highlightbackground=highlightcolor, borderwidth=1)
            # dg = Tk.Frame(self,bg="red")
            dg.columnconfigure(0, weight=1)

            self.widgets["canvas"] = canvas = Tk.Canvas(dg, bg=button_background, highlightbackground=App.background_gray_1)
            # self.widgets["canvas"] = canvas = Tk.Canvas(dg, bg="red")
            win = Tk.Frame(dg, bg=App.background_gray_1)
            winid = canvas.create_window(0, 0, anchor="nw", window=win)

            def resize_frame(e, canvas, winid):
                canvas.itemconfig(winid, width=e.width-1)
                # canvas.itemconfig(winid, height=e.height-1)
                _, _, x, y = canvas.bbox("all")
                canvas.config( scrollregion=(0, 0, x, y+20) )
                canvas.update_idletasks()

            canvas.bind("<Configure>", lambda x:resize_frame(x, canvas, winid))

            self.widgets["downloads_grid"] = win
            for i in range(2,6):
                win.columnconfigure(i, weight=1, pad=5)
            win.columnconfigure(0, weight=3, minsize=200, pad=5)
            win.columnconfigure(1, weight=4, minsize=200, pad=5)
            win.columnconfigure(5, minsize=80)

            for i in [
                {"type": "label", "widget_name": "", "row": 0, "column": 0, "width":0, "text": "Filename",  },
                {"type": "label", "widget_name": "", "row": 0, "column": 1, "width":0, "text": "URL"},
                {"type": "label", "widget_name": "", "row": 0, "column": 2, "width":7, "text": "Progress" },
                {"type": "label", "widget_name": "", "row": 0, "column": 3, "width":7, "text": "Progress %" },
                {"type": "label", "widget_name": "", "row": 0, "column": 4, "width":7, "text": "Speed" },
                {"type": "label", "widget_name": "", "row": 0, "column": 5, "width":7, "text": "Time Left" },
                ]:
                if i["type"] == "label":
                    w = Tk.Label(win, text=i["text"], font=self.progressFont, bg=entry_background_color, fg="white", bd=1, relief="groove")        
                    w.grid(row=i["row"], column=i["column"], sticky="we", ipady=5)

            dg.grid(row=2,column=0, sticky='ew', padx=5, pady=5)
            scrollbar = Tk.Scrollbar(dg, command=canvas.yview, bg=entry_background_color, highlightbackground=entry_background_color)
            scrollbar.grid(row=0, column=1, sticky="ns")
            canvas.grid(row=0,column=0, sticky="new")
            canvas['yscrollcommand'] = scrollbar.set

            # self.update_idletasks()

        # buttons_grid
            
            bg_2 = Tk.Frame(self, bg=App.background_gray_1)
            for i in range(0, 9):
                bg_2.columnconfigure(i, weight=1, pad=5)
            for i in [
                {"widget_name": "btn_remove", "row": 0, "column": 4, "text": "Remove", "command": self.remove_download },
                {"widget_name": "btn_pause", "row": 0, "column":5, "text": "Pause/Resume", "command": self.pause_download },
                {"widget_name": "btn_select_all", "row": 0, "column":6, "text": "(De)Select All", "command": self.select_all },
                ]:
                b = Tk.Button(bg_2, text=i["text"], command=i["command"], bg=button_background, relief="flat")
                self.widgets[i["widget_name"]] = b
                b.grid(row=0, column=i["column"], sticky="", padx=5, pady=2)
            bg_2.grid(row=3,column=0, sticky='ew', padx=5, pady=5)

        # status bar
            sb = Tk.Frame(self, bg=App.background_gray_1)
            sb.columnconfigure(0, weight=1, pad=10)
            sv = Tk.StringVar()
            sv.set("Speed: 0 KB/s")
            self.widgets["lab_status_var"] = sv
            Tk.Label(sb, bg=App.background_gray_1, fg=textcolor, textvariable=sv).grid(row=0, column=0, stick="w")
            sb.grid(row=4,column=0, sticky='ew', padx=5, pady=5)

    def start_on_completion_script(self):
        self.suspend_on_quit = 1
        path = os.path.join(DIR, "background_closer.py")
        os.system("gksudo python '%s' &"% path)
            
    def start_downloads(self):
        pass

    def clear_completed(self):
        # logger_main.debug("clear_completed: pressed")
        for index in range( len(threaded_video_downloader.downloader_instances)-1, -1, -1):
            i = threaded_video_downloader.downloader_instances[index]
            if i.completed:
                logger_main.debug("clear_completed: index completed \n\t\tURL: %s\n\t\tFile: %s", i.url, i.output_filename )
                for widget_name in i.download_labels.keys():
                    i.download_labels[widget_name].grid_forget()
                del threaded_video_downloader.downloader_instances[index]
        pass

    def select_all(self):
        print 1
        found_deselected = 0 
        for index in range( len(threaded_video_downloader.downloader_instances) ): 
            i = threaded_video_downloader.downloader_instances[index]
            widget_name = i.download_labels.keys()[0]
            if not i.download_labels[widget_name].current_mouse_clicked_on_download:
                found_deselected = 1
                break
        if found_deselected:
            for index in range( len(threaded_video_downloader.downloader_instances) ): 
                i = threaded_video_downloader.downloader_instances[index]
                widget_name = i.download_labels.keys()[0]
                # skip already selected
                if i.download_labels[widget_name].current_mouse_clicked_on_download:
                    continue
                for widget_name in i.download_labels.keys():
                    widget = i.download_labels[widget_name]
                    widget.current_mouse_clicked_on_download = 1
                    widget.previous_color =  download_default_color
                    widget.config(bg=mouse_clicked_on_download_color) 
        else:
            for index in range( len(threaded_video_downloader.downloader_instances) ): 
                i = threaded_video_downloader.downloader_instances[index]
                widget_name = i.download_labels.keys()[0]
                # skip already deselected
                if not i.download_labels[widget_name].current_mouse_clicked_on_download:
                    continue
                for widget_name in i.download_labels.keys():
                    widget = i.download_labels[widget_name]
                    widget.current_mouse_clicked_on_download = 0
                    widget.previous_color =  mouse_clicked_on_download_color
                    # widget.config(bg=mouse_clicked_on_download_color) 
                    widget.config(bg=download_default_color) 

    def save_session(self, no_prompt = 0):
        global config_dir

        session_file = os.path.join(config_dir, "previous_sessions.txt")
        with open(session_file, 'w') as w:
            for i in threaded_video_downloader.downloader_instances:
                x = [ str(i) for i in [i.output_filename,  i.continue_, i.segment_size, i.url, i.no_of_segments] ]
                write_string =  "<::>".join(x)
                w.write( "%s\n"%write_string )

        if not no_prompt:
            tkMessageBox.showinfo("Saved!", "Saved Session to Session File.")

    def resume_session(self):
        global config_dir
        if self.session_resumed:
            logger_main.info("resume_session: Session already resumed.")
            return
        logger_main.info("resume_session: Session resuming.")
        self.session_resumed = 1
        session_file = os.path.join(config_dir, "previous_sessions.txt")
        if not os.path.exists(session_file):
            logger_main.info("No session file")
            return 

        w = open(session_file)
        for line in w.readlines():
            # for i in range(4):
                self.output_filename,  continue_, segment_size, url, segments = line.split("<::>")
                # par, child = os.path.split(self.output_filename)
                # child = "%s %s" % (i, child)
                # self.output_filename = os.path.join(par, child)
                self.widgets["cb_continue"].set(1)
                self.widgets["listb_url"].delete('0.0',Tk.END)
                self.widgets["listb_url"].insert('0.0', url)
                self.widgets["e_num_segments"].set(int(segments))
                segment_string = "%s" % (int(segment_size)/1024)
                self.widgets["e_segment_size"].set(segment_string)

                self.add_download()
        w.close()
        self.widgets["listb_url"].delete('0.0',Tk.END)
        pass

    def choose_output(self):
        path = tkFileDialog.asksaveasfilename(initialdir=self.dialog_initial_directory, title="Choose Save as Location:")
        if path:
            self.output_filename = path
            self.dialog_initial_directory = os.path.dirname(path)

    def add_download(self):
        global downloads_grid_row

        previous_seen = len(threaded_video_downloader.downloader_instances)

        if self.output_filename is None:
            tkMessageBox.showerror('Error!', "Choose Output Filename!")
            return

        output_filename = self.output_filename
        self.output_filename = None

        continue_ = self.widgets["cb_continue"].get()
        url = self.widgets["listb_url"].get("0.0", Tk.END).lstrip(" ")
        try:
            segments = int(self.widgets["e_num_segments"].get())
            segment_size = int(eval(self.widgets["e_segment_size"].get())) * 1024
            threaded_video_downloader.concurrent_downloads = int(self.widgets["e_num_downloads"].get())
        except:
            logger_main.error(traceback.format_exc())
            segments = 8
            segment_size = 512*1024
            threaded_video_downloader.concurrent_downloads = 2

        t = threading.Thread(target=threaded_video_downloader.DownloadManager, kwargs={
                    "filename" : output_filename, 
                    "continue_" : continue_,
                    "url" : url,
                    "segment_size": segment_size,
                    "no_of_segments" : segments
                } 
            )
        t.start()

        dg = self.widgets["downloads_grid"]
        row = downloads_grid_row

        while len(threaded_video_downloader.downloader_instances)<= previous_seen:
            # pass
            time.sleep(0.01)

        time.sleep(0.1)

        threaded_video_downloader.downloader_instances[-1].download_labels={}

        for i in [
                {"type": "label", "widget_name": "output_filename", "row": 0, "column": 0, "text": os.path.split(output_filename)[-1],  },
                # {"type": "label", "widget_name": "output_filename", "row": 0, "column": 0, "text": os.path.split(output_filename)[-1][:30],  },
                {"type": "label", "widget_name": "url", "row": 0, "column": 1, "text": url[:60]},
                # {"type": "label", "widget_name": "url", "row": 0, "column": 1, "text": url},
                {"type": "label", "widget_name": "progress", "row": 0, "column": 2, "text": 0},
                {"type": "label", "widget_name": "percentage_written", "row": 0, "column": 3, "text": 0 },
                {"type": "label", "widget_name": "speed", "row": 0, "column": 4, "text": 0 },
                {"type": "label", "widget_name": "time_remaining", "row": 0, "column": 5, "text": 0 },
            ]:
                var = Tk.StringVar()
                var.set(str(i["text"]).strip("\n"))
                w = Tk.Label(dg, font=self.downloadsFont, justify="left", bg=App.background_gray_1, textvariable=var, height=1)     
                if i["widget_name"] == "url":
                    w["width"] = 30
                elif i["widget_name"] != "output_filename":
                    w["width"] = 10
                w.var = var  
                w.row = row
                w.previous_color = download_default_color
                w.config(bg=download_default_color)
                w.downloader_instance = threaded_video_downloader.downloader_instances[-1]
                w.current_mouse_clicked_on_download = 0
                w.bind("<Button-1>", self.download_row_click)
                w.bind("<Enter>", self.download_row_enter)
                w.bind("<Leave>", self.download_row_leave)
                threaded_video_downloader.downloader_instances[-1].download_labels[i["widget_name"]] = w 
                w.grid(row=row, column=i["column"], sticky="wens", pady=3, ipady=5)

        downloads_grid_row += 1
        self.widgets["listb_url"].delete('0.0',Tk.END)

        canvas = self.widgets["canvas"]
        _, _, x, y = canvas.bbox("all")
        canvas.config( scrollregion=(0, 0, x, y+40) )
            
    def remove_download(self):
        index = len(threaded_video_downloader.downloader_instances) - 1
        while index>=0:
            i = threaded_video_downloader.downloader_instances[index]
            lab = i.download_labels["output_filename"]
            if not lab.current_mouse_clicked_on_download:
                index-=1
                continue

            # this item is selected
            i.running = 0
            lab.grid_forget()

            for j in i.download_labels.keys():
                lab = i.download_labels[j]
                lab.grid_forget()

            del threaded_video_downloader.downloader_instances[index]
            index = len(threaded_video_downloader.downloader_instances) - 1

    def pause_download(self):
        for item in threaded_video_downloader.downloader_instances:
            lab = item.download_labels["output_filename"]
            if not lab.current_mouse_clicked_on_download:
                continue

            item.pause = not item.pause

            for j in item.download_labels.keys():
                lab = item.download_labels[j]
                lab.current_mouse_clicked_on_download = 0
                lab.config(bg=download_default_color)

    def pause_resume_all_downloads(self):
        """Sets all items to one state or another. Paused or resumed. Pause is default"""
        any_item_not_paused = 0
        for item in threaded_video_downloader.downloader_instances:
            if not item.pause:
                any_item_not_paused = 1
                break

        for item in threaded_video_downloader.downloader_instances:
            if any_item_not_paused:
                #we have to pause everything
                item.pause = 1
                # restore default color and remove clicking state as stored in app
                for j in item.download_labels.keys():
                    lab = item.download_labels[j]
                    lab.current_mouse_clicked_on_download = 0
                    lab.config(bg=download_default_color)

            else:
                #we resume everything
                item.pause = 0
                # restore default color and remove clicking state as stored in app
                for j in item.download_labels.keys():
                    lab = item.download_labels[j]
                    lab.current_mouse_clicked_on_download = 0
                    lab.config(bg=download_default_color)

    def update_window(self):
        global want_to_exit
        self.after( self.update_interval, self.update_window)
        if want_to_exit:
            self.onquit()

        total_speed = 0
        try:
            all_completed = 1
            try:
                for i in threaded_video_downloader.downloader_instances:
                    try:
                        total_speed += float(i.speed)
                    except:
                        pass
                    if i.completed or i.error:
                        for lab in ["output_filename", "url", "progress", "percentage_written", "speed", "time_remaining"]:
                            if i.download_labels[lab].current_mouse_clicked_on_download or self.current_mouse_over_download:
                                break
                            if i.error:
                                 i.download_labels[lab].config(bg=download_error_color)
                            else:
                                i.download_labels[lab].config(bg=download_completed_color)
                    else:
                        # not all completed
                        all_completed = 0

                    i.download_labels["progress"].var.set(threaded_video_downloader.humansize(i.progress))
                    i.download_labels["percentage_written"].var.set(i.percentage_written)
                    i.download_labels["speed"].var.set(i.speed)
                    i.download_labels["time_remaining"].var.set(i.time_remaining_str)
            except:
                pass

            if all_completed and self.suspend_on_quit:
                # just touch the file
                with open(on_completion_touch_file, 'w') as w:
                    w.write("")
                self.onquit()

            self.widgets["lab_status_var"].set("Speed: {0:.1f} KB/s".format(total_speed) )

        except:
            logger_main.error("update_window: %s", traceback.format_exc() )

    def download_row_enter(self, event):
        self.current_mouse_over_download = 1
        for i in event.widget.downloader_instance.download_labels.keys():
            widget = event.widget.downloader_instance.download_labels[i]
            if widget.current_mouse_clicked_on_download:
                return
            widget.previous_color =  widget.cget("bg")
            widget.config(bg=mouse_over_download_color)

    def download_row_leave(self, event):
        self.current_mouse_over_download = 0
        for i in event.widget.downloader_instance.download_labels.keys():
            widget = event.widget.downloader_instance.download_labels[i]
            if widget.current_mouse_clicked_on_download:
                return
            previous_color = event.widget.downloader_instance.download_labels[i].previous_color
            event.widget.downloader_instance.download_labels[i].config(bg=previous_color)

    def download_row_click(self, event):
        for i in event.widget.downloader_instance.download_labels.keys():
            widget = event.widget.downloader_instance.download_labels[i]
            widget.current_mouse_clicked_on_download = not widget.current_mouse_clicked_on_download
            if not widget.current_mouse_clicked_on_download:
                widget.config(bg=mouse_over_download_color)
                continue
            widget.previous_color =  download_default_color
            widget.config(bg=mouse_clicked_on_download_color) 

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except:
        logger_main.error("Error: %s", traceback.format_exc() )
    logger_main.info("Exiting application")