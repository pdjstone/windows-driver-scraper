# Windows Update Driver Scraping Scripts

This is a collection of scripts I wrote while researching our [WSUSpect talk](https://www.contextis.com/documents/161/CTX_WSUSpect_White_Paper.pdf) for BlackHat 2015. The scripts scrape and analyse data about Windows USB drivers from the Microsoft Update Catalog (http://www.catalog.update.microsoft.com).

The scripts are pretty rough, but they do (mostly) work. They are provided as-is, and mostly unmodified since 2015. They may be useful as a starting point for anyone conducting research in this area. If you do find them useful please let me know!

Run the scripts in the following order:

```
python wucatalogscrape.py - creates the drivers.sqlite database and scrapes basic driver info into it
python fetch_driver_download_urls.py - scrapes and stores the driver download URls
python download_drivers.py - downloads the driver CAB files into the downloads/ directory
python extract.py downloads/*.cab - extracts *.inf and *.pdb files into the extracted/ directory
python anaylse_drivers.py - analyses the extracted files
```

