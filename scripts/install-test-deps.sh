#!/usr/bin/env bash
set -euo pipefail
# Disposable CI environments only. APT still verifies Ubuntu's archive signatures.
update() {
  apt-get -o APT::Update::Error-Mode=any -o Acquire::Retries=0 \
    -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 update -qq
}
if ! update; then
  if ! grep -qx 'ID=ubuntu' /etc/os-release; then
    echo 'APT update failed on a non-Ubuntu environment' >&2
    exit 1
  fi
  echo 'Ubuntu archive unavailable; retrying with the USTC Ubuntu mirror.' >&2
  for source in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/apt-mirrors.txt; do
    [[ -f $source ]] || continue
    sed -i \
      -e 's|https\?://archive\.ubuntu\.com/ubuntu|http://mirrors.ustc.edu.cn/ubuntu|g' \
      -e 's|https\?://azure\.archive\.ubuntu\.com/ubuntu|http://mirrors.ustc.edu.cn/ubuntu|g' \
      -e 's|https\?://security\.ubuntu\.com/ubuntu|http://mirrors.ustc.edu.cn/ubuntu|g' \
      -e 's|https\?://ports\.ubuntu\.com/ubuntu-ports|http://mirrors.ustc.edu.cn/ubuntu-ports|g' \
      "$source"
  done
  update
fi
apt-get install -y --no-install-recommends "$@"
