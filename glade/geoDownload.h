Gtk::Window *window;
Gtk::Window *windowAdd;

Gtk::Entry *entry_Segment_Size;
Gtk::Entry *entry_no_concurrent_dl;
Gtk::Entry *entry_no_segments;
Gtk::Entry *entry_filename;

Gtk::Button *button_add_dl;
Gtk::Button *button_new_dl;
Gtk::Button *button_pause_resume;
Gtk::Button *button_remove;
Gtk::Button *button_dselect_all;
Gtk::Button *button_set_filename;

Gtk::TreeView *treeview1;
Glib::RefPtr<Gtk::ListStore> treemodel;
Glib::RefPtr<Gtk::ListStore> comboboxmodel;

Gtk::ComboBox *combobox_size;

Gtk::CheckButton *checkbutton_continue;

Gtk::TextView *textview_url;

std::string save_as_filename;
std::string url;

int widths[] = {200, 220, 80, 50, 80, 40};
std::vector<int> column_widths(widths, widths + sizeof(widths) / sizeof(int));;

bool continue_new_download_from_previous;

//functions
bool checkValidNumeric(const std::string &s);
void set_initial_values();
void getUrl();
void getContinueForNewFile();

//classes
class SignalHandler{
	public:
		void on_button_add_dl_clicked();
		void on_button_new_dl_clicked();
		bool on_entry_segment_size_focus_out(bool x);
		bool on_entry_no_segments_focus_out(bool x);
		bool on_entry_no_concurrent_dl_focus_out(bool x);
		void on_button_set_filename_clicked();
};

SignalHandler sh;

class ModelColumns : public Gtk::TreeModel::ColumnRecord
{
	public:
		ModelColumns()
		{ 
			add(Filename); 
			add(url); 
			add(size); 
			add(percentage_complete); 
			add(time_left); 
			add(action); 
		}

		Gtk::TreeModelColumn<Glib::ustring> Filename;
		Gtk::TreeModelColumn<Glib::ustring> url;
		Gtk::TreeModelColumn<Glib::ustring> size;
		Gtk::TreeModelColumn<Glib::ustring> percentage_complete;
		Gtk::TreeModelColumn<Glib::ustring> time_left;
		Gtk::TreeModelColumn<Glib::ustring> action;
		Gtk::TreeModelColumn<std::shared_ptr<DownloadItem>> download_item;
};
ModelColumns columns;
class ComboColumns : public Gtk::TreeModel::ColumnRecord
{
	public:
		ComboColumns()
		{ 
			add(size); 
		}

		Gtk::TreeModelColumn<Glib::ustring> size;
};
ComboColumns combo_columns;
