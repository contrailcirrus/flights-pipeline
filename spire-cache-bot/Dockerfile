
FROM debian:trixie-slim

RUN apt-get -y update && apt-get -y install curl

WORKDIR /
COPY ping_api.sh .

ENV CONTRAILS_API_KEY="foo"

ENTRYPOINT bash ping_api.sh
