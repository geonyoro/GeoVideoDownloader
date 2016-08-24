bool SignalHandler::on_entry_segment_size_focus_out(bool x){
	std::string s = entry_Segment_Size->get_text();
	std::cout << s << " ::: " << checkValidNumeric(s) << std::endl;
}


bool SignalHandler::on_entry_no_segments_focus_out(bool x){
	std::string s = entry_no_segments->get_text();
	std::cout << s << " ::: " << checkValidNumeric(s) << std::endl;
}

bool SignalHandler::on_entry_no_concurrent_dl_focus_out(bool x){
	std::string s = entry_no_concurrent_dl->get_text();
	std::cout << s << " ::: " << checkValidNumeric(s) << std::endl;
}
void SignalHandler::on_button_add_dl_clicked(){
	windowAdd->show();
	std::cout << "Add New Download" << std::endl;
}
void SignalHandler::on_button_new_dl_clicked(){
	//filename has already been set by dialog
	getUrl();
	getContinueForNewFile();
	windowAdd->hide();
	std::cout << "New Download Added: Url: " << url << "\t" << "Filename:" << save_as_filename <<  "\tContinue:" << continue_new_download_from_previous <<std::endl;
}
void SignalHandler::on_button_set_filename_clicked(){
	Gtk::FileChooserDialog dialog("Please choose a folder", Gtk::FILE_CHOOSER_ACTION_SAVE  );
	//dialog.set_transient_for(*window);

	dialog.add_button("_Cancel", Gtk::RESPONSE_CANCEL);
	dialog.add_button("Select", Gtk::RESPONSE_OK);

	int result = dialog.run();

	//Handle the response:
	switch(result)
	{
		case(Gtk::RESPONSE_OK):
			{
				save_as_filename = dialog.get_filename();
				boost::filesystem::path boost_path(save_as_filename);	
				std::string shortened_filename = boost_path.filename().native();
				std::cout <<  shortened_filename << std::endl;
				entry_filename->set_text(shortened_filename);
				break;
			}
		case(Gtk::RESPONSE_CANCEL):
			{
				//std::cout << "Cancel clicked." << std::endl;
				break;
			}
		default:
			{
				//std::cout << "Unexpected button clicked." << std::endl;
				break;
			}
	}
}

