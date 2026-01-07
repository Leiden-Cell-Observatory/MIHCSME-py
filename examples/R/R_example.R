#Author Maarten Paul, m.w.paul@lacdr.leidenuniv.nl

if(!require("pacman")){install.packages("pacman")}
#Install R-python reticualte package
pacman::p_load(reticulate)
pacman::p_load(rspacer)

use_virtualenv("~/.virtualenvs/r-reticulate")
py_discover_config()

# OMERO and mihcsme dependencies
py_require("pandas")
py_require("zeroc_ice @ https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp312-cp312-manylinux_2_28_x86_64.whl")
#for Linux/Mac find the right whl https://www.glencoesoftware.com/blog/2023/12/08/ice-binaries-for-omero.html also match your Python version!
py_require("ezomero[tables]") #make use of pandas tables
#ezomero <- import("pandas",convert = FALSE)
ezomero <- import("ezomero",convert = FALSE)
py_require("mihcsme-py@git+https://github.com/Leiden-Cell-Observatory/mihcsme-py.git")
mihcsme <- import("mihcsme_py")

#fetch template from Rspace
api_status()

new_file <- rspacer::file_upload("MIHCSME Template_MH.xlsx")
file <- rspacer::file_download(new_file$globalId)

metadata <- mihcsme$parse_excel_to_model(file)

metadata$investigation_information$data_owner
metadata$investigation_information$data_owner$first_name

metadata$assay_conditions

#setup OMERO connection
conn <- ezomero$connect(user="root",password="omero",host="localhost",port=4064,group="system",secure=TRUE)

omero_metadata = mihcsme$download_metadata_from_omero(conn, "Screen", 51)
omero_metadata$assay_conditions






