To make the OMERO.script for MIHCSME-py available  on your OMERO server, add the following to the Dockerfile of OMERO.server.

Download the script from the Github repository.
```
# Install the Upload_MIHCSME_Metadata script
RUN curl -o $OMERO_DIST/lib/scripts/omero/annotation_scripts/Upload_MIHCSME_Metadata.py \
    https://raw.githubusercontent.com/Leiden-Cell-Observatory/MIHCSME-py/refs/heads/main/scripts/Upload_MIHCSME_Metadata.py
```

Install the package from github (for now).
```
RUN /opt/omero/server/venv3/bin/python3 -m pip install --upgrade pip
RUN /opt/omero/server/venv3/bin/python3 -m pip install git+https://github.com/Leiden-Cell-Observatory/mihcsme-py.git
```
