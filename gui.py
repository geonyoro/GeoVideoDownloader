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
from geon_downloader import *

exit_app = threading.Event()

downloads_grid_row = 1

class App(Tk.Frame):
    background_gray_1 = "#f8f8f8"
    def __init__(self):
        Tk.Frame.__init__(self, bg=App.background_gray_1)
        self.update_interval = 50

        self.output_filename = None

        self.dialog_initial_directory = os.path.dirname(__file__)

        self.bigFont = tkFont.Font(root=self.master, size=12, underline=1)
        self.progressFont=tkFont.Font(root=self.master, size=10, underline=1)
        
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        self.master.title("GeoN Download Manager")
        self.master.geometry("{0}x{1}+100+0".format(1000,620))
        self.widgets={}

        # resizing
        self.columnconfigure(0, weight=1)
        # self.columnconfigure(2, weight=1)
        self.basic_widgets()

        self.grid(row=0,column=0, sticky="nsew")
        self.master.protocol("WM_DELETE_WINDOW", self.onquit) 

        self.after( self.update_interval, self.update_window) 

    def update_window(self):
        pass

    def onquit(self):
        global exit_app

        for i in downloader_instances:
            i.running = 0

        exit_app.set()
        self.master.destroy()
        self.master.quit()

    def basic_widgets(self):
        # button_grid
            bg = Tk.Frame(self, bg=App.background_gray_1)
            for i in [
                {"widget_name": "btn_start", "row": 0, "column": 0, "text": "Start",   "command": self.start_downloads },
                {"widget_name": "btn_clear_completed", "row": 0, "column": 1, "text": "Clear Completed Downloads", "command": self.clear_completed },
                {"widget_name": "btn_save_session", "row": 0, "column": 2, "text": "Save Session", "command": self.save_session },
                {"widget_name": "btn_resume_session", "row": 0, "column": 3, "text": "Resume Session", "command": self.resume_session },
            ]:
                b = Tk.Button(bg, text=i["text"], command=i["command"])
                self.widgets[i["widget_name"]] = b
                b.grid(row=0, column=i["column"], sticky="", padx=5)

            bg.grid(row=0,column=0)

        # input_grid
            ig = Tk.Frame(self, bg=App.background_gray_1)
            widths = 70
            for i in range(2):
                bg.columnconfigure(i, weight=1)
            for i in [
                {"type": "label", "widget_name": "", "row": 1, "column": 0, "text": "Output Filename:",  },
                {"type": "label", "widget_name": "", "row": 2, "column": 0, "text": "Continue:" },
                {"type": "label", "widget_name": "", "row": 3, "column": 0, "text": "URL:" },
                {"type": "label", "widget_name": "", "row": 4, "column": 0, "text": "Number of Segments:" },
                {"type": "label", "widget_name": "", "row": 5, "column": 0, "text": "UserAgent:" },

                {"type": "button", "widget_name": "", "columnspan": 1, "row": 1, "column": 1, "text": "Choose Output", "command": self.choose_output},

                {"type": "listb", "row": 3, "column": 1, "widget_name": "listb_url", "text":
                    "https://captbbrucato.files.wordpress.com/2011/08/dscf0585_stitch-besonhurst-2.jpg" },
                {"type": "listb", "row": 5, "column": 1, "widget_name": "listb_user_agent", "text": 
                    "Mozilla/5.0 (Windows NT 5.2; rv:2.0.1) Gecko/20100101 Firefox/4.0.1"},

                {"type": "checkb", "row": 2, "column": 1, "default_state": 1, "widget_name": "cb_continue" },
                {"type": "checkb", "row": 4, "column": 1, "default_state": 0, "widget_name": "cb_num_segments" },

                {"type": "button", "widget_name": "btn_add", "row": 7, "column": 0, "columnspan": 2, "text": "Add", "command": self.add_download },
                
                {"type": "separat", "row": 6, "column": 0, "columnspan": 2 },
                {"type": "separat", "row": 0, "column": 0, "columnspan": 2 }
            ]:
                if i["type"] == "label":
                    w = Tk.Label(ig, text=i["text"], bg=App.background_gray_1)
                    w.grid(row=i["row"], column=i["column"], sticky="e")

                elif i["type"] == "entry": 
                    var = Tk.StringVar()
                    var.set(i["text"])
                    self.widgets[i["widget_name"]] = var
                    w = Tk.Entry(ig, bg=App.background_gray_1, width=widths, textvariable=var)
                    w.grid(row=i["row"], column=i["column"], sticky="ew", padx=8)

                elif i["type"] == "checkb":
                    var = Tk.IntVar()
                    var.set(i["default_state"])
                    self.widgets[i["widget_name"]] = var
                    w = Tk.Checkbutton(ig, bg=App.background_gray_1, variable=var)
                    w.grid(row=i["row"], column=i["column"], sticky="", padx=8, pady=5)

                elif i["type"] == "listb":
                    w = Tk.Text(ig, bg=App.background_gray_1, height=2, width=widths)
                    self.widgets[i["widget_name"]] = w
                    w.insert('0.0', i['text'] )
                    w.grid(row=i["row"], column=i["column"], sticky="ew", padx=8, pady=5)

                elif i["type"] == "button":
                    b = Tk.Button(ig, text=i["text"], command=i["command"])
                    self.widgets[i["widget_name"]] = b
                    b.grid(row=i["row"], column=i["column"], columnspan=i["columnspan"], sticky="", padx=5, ipadx=60)

                elif i["type"] == "separat":
                    ttk.Separator(ig, orient=Tk.HORIZONTAL).grid(row=i["row"], column=i["column"], columnspan=i["columnspan"], sticky="ew", padx=5, pady=10)    

            ig.grid(row=1,column=0)

        # downloads_grid
            dg = Tk.Frame(self)
            self.widgets["downloads_grid"] = dg
            for i in range(4):
                dg.columnconfigure(i, weight=5)
            dg.columnconfigure(4, weight=1)

            for i in [
                {"type": "label", "widget_name": "", "row": 0, "column": 0, "text": "Output Filename",  },
                {"type": "label", "widget_name": "", "row": 0, "column": 1, "text": "URL"},
                {"type": "label", "widget_name": "", "row": 0, "column": 2, "text": "Progress" },
                {"type": "label", "widget_name": "", "row": 0, "column": 3, "text": "Progress %" },
                {"type": "label", "widget_name": "", "row": 0, "column": 4, "text": "Speed" },
                ]:
                if i["type"] == "label":
                    w = Tk.Label(dg, text=i["text"])        
                    w.grid(row=i["row"], column=i["column"], sticky="we")

            dg.grid(row=2,column=0, sticky='ew', padx=5, pady=5)

        #lower_button_grid
            bg2 = Tk.Frame(self, bg=App.background_gray_1)
            b = Tk.Button(bg2, text="Remove", command=self.remove_download)
            self.widgets["btn_remove"] = b
            b.grid(row=0, column=0, sticky="", padx=5, ipadx=47, pady=10)
            bg2.grid(row=3, column=0)

    def start_downloads(self):
        print "start_downloads"
        pass

    def clear_completed(self):
        print "clear_completed"
        pass

    def save_session(self):
        print "save_session"
        pass

    def resume_session(self):
        print "resume_session"
        pass

    def choose_output(self):
        path = tkFileDialog.asksaveasfilename(initialdir=self.dialog_initial_directory, title="Choose Save as Location:")
        self.output_filename = path
        self.dialog_initial_directory = os.path.dirname(path)

    def add_download(self):
        global downloader_instances, downloads_grid_row

        if self.output_filename is None:
            return

        output_filename = os.path.split(self.output_filename)[-1]
        self.output_filename = None

        download_continue = self.widgets["cb_continue"].get()
        url = self.widgets["listb_url"].get("0.0", Tk.END).lstrip(" ")
        user_agent = self.widgets["listb_user_agent"].get("0.0", Tk.END)

        old_length = len(downloader_instances)
        t = threading.Thread(target=Downloader, kwargs={
                    "output_filename" : output_filename, 
                    "download_continue" : download_continue,
                    "url" : url,
                    "user_agent" : user_agent
                } 
            )
        t.start()

        dg = self.widgets["downloads_grid"]
        row = downloads_grid_row

        time.sleep(1)

        downloader_instances[-1].download_labels={}
        for i in [
                {"type": "label", "widget_name": "output_filename", "row": 0, "column": 0, "text": output_filename,  },
                {"type": "label", "widget_name": "url", "row": 0, "column": 1, "text": url},
                {"type": "label", "widget_name": "progress", "row": 0, "column": 2, "text": 0},
                {"type": "label", "widget_name": "progress_percent", "row": 0, "column": 3, "text": 0 },
                {"type": "label", "widget_name": "speed", "row": 0, "column": 4, "text": 0 },
            ]:
                var = Tk.StringVar()
                var.set(i["text"])
                w = Tk.Label(dg, bg=App.background_gray_1, textvariable=var)     
                w.var = var  
                downloader_instances[-1].download_labels[i["widget_name"]] = w 
                w.grid(row=row, column=i["column"], sticky="wens")

        downloads_grid_row += 1
            
    def remove_download(self):
        print "remove_download"
        pass

    def update_window(self):
        # print "update_window"
        try:
            for i in downloader_instances:
                if i.completed:
                    for lab in ["output_filename", "url", "progress", "progress_percent", "speed"]:
                        i.download_labels[lab].config(bg="#06E1DF")
                i.download_labels["progress"].var.set(i.progress)
                i.download_labels["progress_percent"].var.set(i.progress_percent)
                i.download_labels["speed"].var.set(i.speed)

        except:
            pass
        self.after( self.update_interval, self.update_window)

if __name__ == "__main__":
    app = App()
    app.mainloop()