class DownloadItem{
	public:
		DownloadItem();
		DownloadItem(std::string name, std::string url);

		float getProgress();
		void startDownload();

		int getSize();
		void setSize(int size);

		

	private:
		int _size;
		float _progress;
};
