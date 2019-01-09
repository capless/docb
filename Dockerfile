FROM python:3.6
RUN mkdir code
WORKDIR code
ADD . /code/docb
ADD ./requirements.txt /code/requirements.txt
ADD ./test_requirements.txt /code/test_requirements.txt
RUN pip install virtualenv
RUN virtualenv ve && /code/ve/bin/pip install -U pip
RUN /code/ve/bin/pip install -r /code/requirements.txt
RUN /code/ve/bin/pip install -r /code/test_requirements.txt
WORKDIR /code/docb
