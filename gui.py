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

from geon_downloader import *

logger_main = logging.getLogger('GUI')
logger_main.setLevel(logging.DEBUG)
logger_main.addHandler(file_handler)
exit_app = threading.Event()

want_to_exit = 0
shown_message_want_to_exit = 0

downloads_grid_row = 1

#config directory
config_dir = os.path.join(os.environ["HOME"], ".geon_downloader")
if not os.path.exists(config_dir):
    os.mkdir(config_dir)

def humansize(nbytes):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    if nbytes == 0: return '0 B'
    i = 0
    while nbytes >= 1024 and i < len(suffixes)-1:
        nbytes /= 1024.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, suffixes[i])

class App(Tk.Frame):
    background_gray_1 = "#f8f8f8"
    def __init__(self):
        Tk.Frame.__init__(self, bg=App.background_gray_1)
        self.current_mouse_over_download = 0
        self.current_mouse_clicked_on_download = 0

        self.update_interval = 50

        self.output_filename = None

        # self.master.wm_iconbitmap("@geondownloader.xbm")

        self.dialog_initial_directory = os.path.join(os.environ["HOME"],"Videos")

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
        self.master.protocol("WM_DELETE_WINDOW", lambda: self.onquit(button_press=1) ) 

        self.after( self.update_interval, self.update_window) 

    def update_window(self):
        pass

    def onquit(self, button_press = 0):
        global exit_app, want_to_exit, shown_message_want_to_exit

        for i in downloader_instances:
            i.running = 0
        if button_press:
            shown_message_want_to_exit = 0

        if len( threading.enumerate() ) > 1 :
            if not shown_message_want_to_exit:
                logger_main.info("Showing message for exit.")

                win = Tk.Toplevel() 
                win.lift()
                l = Tk.Label(win, text = "Closing all background Downloaders...\nWill exit the app after finished.").grid()
                win.title("Title")
                win.update_idletasks()
                start = win.winfo_geometry().split("+")[0]
                win.geometry("+".join([start, "300", "300"]))
                
                win.transient(self.master)
                win.overrideredirect(True)
                
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
                {"widget_name": "btn_save_session", "row": 0, "column": 2, "text": "     Save Session     ", "command": self.save_session },
                {"widget_name": "btn_resume_session", "row": 0, "column": 3, "text": "   Resume Session   ", "command": self.resume_session },
            ]:
                b = Tk.Button(bg, text=i["text"], command=i["command"], bg="#FFFC94", relief="flat")
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
                {"type": "label", "widget_name": "", "row": 4, "column": 0, "text": "Number of Segments:" },
                {"type": "label", "widget_name": "", "row": 5, "column": 0, "text": "UserAgent:" },

                {"type": "button", "widget_name": "", "columnspan": 1, "row": 1, "ipadx": 0, "column": 0, "columnspan": 2, "text": "Choose Output Filename", "command": self.choose_output},

                # {"type": "listb", "row": 3, "column": 1, "widget_name": "listb_url", "text":
                #     "https://captbbrucato.files.wordpress.com/2011/08/dscf0585_stitch-besonhurst-2.jpg" },
                {"type": "listb", "row": 3, "column": 1, "widget_name": "listb_url", "text":
                    "" },

                {"type": "listb", "row": 5, "column": 1, "widget_name": "listb_user_agent", "text": 
                    "Mozilla/5.0 (Windows NT 5.2; rv:2.0.1) Gecko/20100101 Firefox/4.0.1"},

                {"type": "checkb", "row": 2, "column": 1, "default_state": 1, "widget_name": "cb_continue" },
                
                {"type": "entry", "row": 4, "column": 1, "default_state": 0, "text":1, "width":2, "widget_name": "cb_num_segments" },

                {"type": "button", "widget_name": "btn_add", "row": 7, "column": 0, "ipadx": 60, "columnspan": 2, "text": "Add", "command": self.add_download },
                
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
                    w = Tk.Entry(ig, bg="#E8FFFC", width=widths, textvariable=var, relief="flat")
                    if i.has_key("width"):
                        w.config(width=i["width"])
                    w.grid(row=i["row"], column=i["column"], sticky="w", padx=8, ipadx=3)

                elif i["type"] == "checkb":
                    var = Tk.IntVar()
                    var.set(i["default_state"])
                    self.widgets[i["widget_name"]] = var
                    w = Tk.Checkbutton(ig, bg=App.background_gray_1, variable=var)
                    w.grid(row=i["row"], column=i["column"], sticky="w", padx=8, pady=5)

                elif i["type"] == "listb":
                    w = Tk.Text(ig, bg="#E8FFFC", height=2, width=widths, relief="flat")
                    self.widgets[i["widget_name"]] = w
                    w.insert('0.0', i['text'] )
                    w.grid(row=i["row"], column=i["column"], sticky="ew", padx=8, pady=5)

                elif i["type"] == "button":
                    b = Tk.Button(ig, text=i["text"], command=i["command"], bg="#FFFC94", relief="flat")
                    self.widgets[i["widget_name"]] = b
                    b.grid(row=i["row"], column=i["column"], columnspan=i["columnspan"], sticky="", padx=5, ipadx=i["ipadx"])

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
                    w = Tk.Label(dg, text=i["text"], bg="#94C9FF", bd=1, relief="groove")        
                    w.grid(row=i["row"], column=i["column"], sticky="we", ipady=5)

            dg.grid(row=2,column=0, sticky='ew', padx=5, pady=5)

        #lower_button_grid
            bg2 = Tk.Frame(self, bg=App.background_gray_1)
            b = Tk.Button(bg2, text="Remove", command=self.remove_download, bg="#FFFC94", relief="flat")
            self.widgets["btn_remove"] = b
            b.grid(row=0, column=0, sticky="", padx=5, ipadx=47, pady=10)
            bg2.grid(row=3, column=0)

    def start_downloads(self):
        # print "start_downloads"
        pass

    def clear_completed(self):
        # print "clear_completed"
        logger_main.debug("clear_completed: pressed")
        for index in range( len(downloader_instances)-1, -1, -1):
            i = downloader_instances[index]
            if i.completed:
                logger_main.debug("clear_completed: index completed \n\t\tURL: %s\n\t\tFile: %s", i.url, i.output_filename )
                for widget_name in i.download_labels.keys():
                    i.download_labels[widget_name].grid_forget()
                del downloader_instances[index]
        pass

    def save_session(self):
        global config_dir
        session_file = os.path.join(config_dir, "previous_sessions.txt")
        with open(session_file, 'w') as w:
            for i in downloader_instances:
                x = [ str(i) for i in [i.output_filename,  i.download_continue, i.user_agent, i.url] ]
                write_string =  "<::>".join(x)
                w.write( "%s\n"%write_string )

        tkMessageBox.showinfo("Saved!", "Saved Session to session_file.")

    def resume_session(self):
        global config_dir
        session_file = os.path.join(config_dir, "previous_sessions.txt")
        w = open(session_file)
        for line in w.readlines():
            self.output_filename,  download_continue, user_agent, url = line.split("<::>")
            self.widgets["cb_continue"].set(int(download_continue))
            self.widgets["listb_url"].delete('0.0',Tk.END)
            self.widgets["listb_url"].insert('0.0', url)
            self.widgets["listb_user_agent"].delete('0.0',Tk.END)
            self.widgets["listb_user_agent"].insert('0.0', user_agent)
            self.add_download()
        w.close()
        pass

    def choose_output(self):
        path = tkFileDialog.asksaveasfilename(initialdir=self.dialog_initial_directory, title="Choose Save as Location:")
        if path:
            self.output_filename = path
            self.dialog_initial_directory = os.path.dirname(path)

    def add_download(self):
        global downloader_instances, downloads_grid_row

        previous_seen = len(downloader_instances)

        if self.output_filename is None:
            tkMessageBox.showerror('Error!', "Choose Output Filename!")
            return

        output_filename = self.output_filename
        self.output_filename = None

        download_continue = self.widgets["cb_continue"].get()
        url = self.widgets["listb_url"].get("0.0", Tk.END).lstrip(" ")
        user_agent = self.widgets["listb_user_agent"].get("0.0", Tk.END)

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

        while len(downloader_instances)<= previous_seen:
            # pass
            time.sleep(0.01)
            # print len(downloader_instances), previous_seen

        time.sleep(0.1)

        downloader_instances[-1].download_labels={}

        for i in [
                {"type": "label", "widget_name": "output_filename", "row": 0, "column": 0, "text": os.path.split(output_filename)[-1][:30],  },
                {"type": "label", "widget_name": "url", "row": 0, "column": 1, "text": url[:30]},
                {"type": "label", "widget_name": "progress", "row": 0, "column": 2, "text": 0},
                {"type": "label", "widget_name": "progress_percent", "row": 0, "column": 3, "text": 0 },
                {"type": "label", "widget_name": "speed", "row": 0, "column": 4, "text": 0 },
            ]:
                var = Tk.StringVar()
                var.set(str(i["text"]).strip("\n"))
                w = Tk.Label(dg, bg=App.background_gray_1, textvariable=var)     
                w.var = var  
                w.row = row
                w.previous_color = "#E6E6E6"
                w.config(bg="#E6E6E6")
                w.downloader_instance = downloader_instances[-1]
                w.current_mouse_clicked_on_download = 0
                w.bind("<Button-1>", self.download_row_click)
                w.bind("<Enter>", self.download_row_enter)
                w.bind("<Leave>", self.download_row_leave)
                downloader_instances[-1].download_labels[i["widget_name"]] = w 
                w.grid(row=row, column=i["column"], sticky="wens", pady=3, ipady=5)

        downloads_grid_row += 1
            
    def remove_download(self):
        for i in downloader_instances:
            skip = 0
            for j in i.download_labels.keys():
                lab = i.download_labels[j]
                if not lab.current_mouse_clicked_on_download:
                    skip = 1
                    break
                i.running = 0
                lab.grid_forget()
            if skip:
                continue
        pass

    def update_window(self):
        # print "update_window"
        global want_to_exit
        self.after( self.update_interval, self.update_window)
        if want_to_exit:
            self.onquit()

        try:
            for i in downloader_instances:
                if i.completed:
                    for lab in ["output_filename", "url", "progress", "progress_percent", "speed"]:
                        if i.download_labels[lab].current_mouse_clicked_on_download or self.current_mouse_over_download:
                            break
                        i.download_labels[lab].config(bg="#06E1DF")
                i.download_labels["progress"].var.set(humansize(i.progress))
                i.download_labels["progress_percent"].var.set(i.progress_percent)
                i.download_labels["speed"].var.set(i.speed)

        except:
            logger.error("update_window: %s", traceback.format_exc() )

    def download_row_enter(self, event):
        self.current_mouse_over_download = 1
        for i in event.widget.downloader_instance.download_labels.keys():
            widget = event.widget.downloader_instance.download_labels[i]
            if widget.current_mouse_clicked_on_download:
                return
            widget.previous_color =  widget.cget("bg")
            widget.config(bg="#FF9A9A")

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
                widget.config(bg="#FF9A9A")
                continue
            widget.previous_color =  "#E6E6E6"
            widget.config(bg="#BEFFC6") 

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except:
        logger_main.error("Error: %s", traceback.format_exc() )
    logger_main.info("Exiting application")