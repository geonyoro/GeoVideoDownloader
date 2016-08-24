#include <gtkmm.h>
#include <iostream>
#include <string>
#include <boost/filesystem.hpp>

#include <curlpp/cURLpp.hpp>
#include <curlpp/Exception.hpp>

#include "DownloadItem.h"
#include "geoDownload.h"
#include "SignalHandler.h"

bool checkValidNumeric(const std::string &s){
	std::string::const_iterator it = s.begin();
	while (it != s.end() && std::isdigit(*it)) ++it;
	return !s.empty() && it == s.end();
}


void set_initial_values(){
	entry_Segment_Size->set_text("300");
	entry_no_segments->set_text("5");
	entry_no_concurrent_dl->set_text("2");
}

void setup_model(){
	{
		//treeview
		treemodel = Gtk::ListStore::create(columns);	
		treeview1->set_model(treemodel);
		treeview1->append_column("Filename", columns.Filename);
		treeview1->append_column("Url", columns.url);
		treeview1->append_column("Size", columns.size);
		treeview1->append_column("%", columns.percentage_complete);
		treeview1->append_column("Time Left", columns.time_left);
		treeview1->append_column("Action", columns.action);

		//make all columns resizeable and set width
		std::vector<Gtk::TreeViewColumn*> tv_columns = treeview1->get_columns();	
		std::vector<Gtk::TreeViewColumn*>::iterator iter = tv_columns.begin();
		int count = 0;
		for (; iter!=tv_columns.end(); iter++, count++){
			Gtk::TreeViewColumn* col = *iter;
			col->set_resizable(true);
			col->set_fixed_width(column_widths[count]);
		}
		Gtk::TreeModel::Row row = *(treemodel->append());
		row[columns.Filename] = "33";
		row[columns.url] = "SFDSD";

		Gtk::TreeModel::Children children = treemodel->children();
		for(Gtk::TreeModel::Children::iterator iter = children.begin(); iter != children.end(); ++iter){
			Gtk::TreeModel::Row row = *iter;
			row->set_value(0, (Glib::ustring)"asdfaksdhfakshdfklasjdfhklsafdhlaskjdhflksajdhfasdfads");
			row->set_value(4, (Glib::ustring)"asdfads");
		}
	}
	{
		comboboxmodel = Gtk::ListStore::create(combo_columns);	
		combobox_size->set_model(comboboxmodel);
		Gtk::TreeModel::Row row = *(comboboxmodel->append());
		combobox_size->set_id_column(0);
		Gtk::CellRendererText *cell = new Gtk::CellRendererText(); 
		combobox_size->pack_start(*cell);
		combobox_size->add_attribute(*cell, "text", combo_columns.size); 
		row[combo_columns.size] = "kB";
		(*(comboboxmodel->append()))[combo_columns.size] = "MB";
		combobox_size->set_active(0);
	}
}
void getContinueForNewFile(){
	continue_new_download_from_previous = checkbutton_continue->get_active();
}

void getUrl(){
	//get the actual Url
	Gtk::TextBuffer::iterator start, end;
	Glib::RefPtr<Gtk::TextBuffer> buffer = textview_url->get_buffer();
	buffer->get_bounds (start, end);
	url = buffer->get_text(start, end, FALSE);
}
int main(int argc, char *argv[])
{
	auto app = Gtk::Application::create(argc, argv, "com.possumcode.geodownloader");
	Glib::RefPtr<Gtk::Builder> builder = Gtk::Builder::create_from_file("gui2.glade");

	SignalHandler sh = SignalHandler(); 

	//get widgets
	builder->get_widget("entry_segment_size", entry_Segment_Size);
	builder->get_widget("entry_no_segments", entry_no_segments);
	builder->get_widget("entry_no_concurrent_dl", entry_no_concurrent_dl);
	builder->get_widget("entry_filename", entry_filename);
	builder->get_widget("combobox_size", combobox_size);
	builder->get_widget("treeview1", treeview1);
	builder->get_widget("window1", window);
	builder->get_widget("windowAdd", windowAdd);
	builder->get_widget("button_add_dl", button_add_dl);
	builder->get_widget("button_new_dl", button_new_dl);
	builder->get_widget("button_pause_resume", button_pause_resume);
	builder->get_widget("button_remove", button_remove);
	builder->get_widget("button_dselect_all", button_dselect_all);
	builder->get_widget("button_set_filename", button_set_filename);
	builder->get_widget("checkbutton_continue", checkbutton_continue);
	builder->get_widget("textview_url", textview_url);

	Glib::RefPtr<Gtk::ListStore> liststore1 = Glib::RefPtr<Gtk::ListStore>::cast_static(builder->get_object("liststore1"));
	Glib::RefPtr<Gtk::ListStore> liststore2 = Glib::RefPtr<Gtk::ListStore>::cast_static(builder->get_object("liststore2"));

	entry_Segment_Size->signal_focus_out_event().connect(sigc::mem_fun(sh, &SignalHandler::on_entry_segment_size_focus_out));
	entry_no_concurrent_dl->signal_focus_out_event().connect(sigc::mem_fun(sh, &SignalHandler::on_entry_no_concurrent_dl_focus_out));
	entry_no_segments->signal_focus_out_event().connect(sigc::mem_fun(sh, &SignalHandler::on_entry_no_segments_focus_out));
	button_add_dl->signal_clicked().connect(sigc::mem_fun(sh, &SignalHandler::on_button_add_dl_clicked));
	button_new_dl->signal_clicked().connect(sigc::mem_fun(sh, &SignalHandler::on_button_new_dl_clicked));
	button_set_filename->signal_clicked().connect(sigc::mem_fun(sh, &SignalHandler::on_button_set_filename_clicked));

	set_initial_values();
	setup_model();

	return app->run(*window);
}
