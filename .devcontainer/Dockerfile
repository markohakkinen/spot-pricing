FROM python:3.12.1

RUN apt-get update && apt-get install -y git sudo

ARG USERNAME=developer
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME
USER $USERNAME
ENV PATH=$PATH:/home/$USERNAME/.local/bin

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
