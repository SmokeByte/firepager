pagerreadme

This is a project I designed to receive tones from a department radio and send out an email or sms text to members.

This will recognize two tone from the department radio 1188hz and 1000hz

This should run in ubuntu ive used python3
It will need to be run in a virtual environment

Need to install the following
pip install numpy
pip install scipy
pip install ffmpeg
pip install twilio
pip install openai-whisper
pip install sounddevice

fire_pager.py is email only
Pager.py is sms and text

You will need a twilio account or similar for sms 

