CREATE TABLE visited (
	vid text,
	page int,
	total_pages int,
	timestamp datetime default current_timestamp
);

CREATE TABLE drivers (
	usb_vid text, 
	title text,
	guid text unique,
	date date,
	version text,
	classification text,
	products text,
	download_size int,
	revision_id int,
	download_url text,
	download_digest text,
	has_umdf_driver int,
	has_userland_service int
);
	
CREATE TABLE usb_ids (
	download_digest text,
	dirname text, 
	inf_file text, 
	usbid text
);
	
CREATE TABLE notable_files (
	download_digest text,
	path text, 
	type text,
	file_digest text, 
	file_size int
)