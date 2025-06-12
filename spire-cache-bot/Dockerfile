
FROM debian:trixie-slim

RUN apt-get -y update && apt-get -y install curl

WORKDIR /
COPY ping_api.sh .

ENTRYPOINT bash ping_api.sh