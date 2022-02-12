FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
    autoconf \
    build-essential \
    sudo \
    wget \
    curl \
    git-all \
    iproute2 \
    iputils-ping \
    net-tools \
    netcat \
    tcpdump \
    unzip \
    psmisc \
    python3 python3-pip python3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
RUN pip3 install subprocess32 pandas python-dotenv

RUN mkdir -p /autograder
COPY . /autograder/source
RUN ln -s /autograder/source/run_autograder /autograder/run_autograder && ln -s /autograder/source/.env /autograder/.env

RUN bash /autograder/source/setup.sh

VOLUME [/autograder/submission, /autograder/results]
WORKDIR /autograder
CMD /autograder/run_autograder
