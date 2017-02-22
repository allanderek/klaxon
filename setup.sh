if [ ! -d "generated" ]; then
    mkdir generated
fi
virtualenv -p /usr/bin/python3 generated/venv
source develop.sh
pip install -r requirements.txt
npm install phantomjs-prebuilt