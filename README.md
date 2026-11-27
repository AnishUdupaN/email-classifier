This is an email classification script that runs every 6 hours in the device, runs it through an ai model in ollama, classifies, and informs the user with an installed app on their phone.


you have to fetch the serviceAccountKey.json and google-services.json yourself and replace that with mine.<br>
serviceAccountKey.json is not provided in here.<br>

## How to Use

clone the repo.<br>
copy the email-check.service and email-check.timer to ~/.config/systemd/user and enable the email-check.timer.<br>
You might have to edit some parts of this project as I have added many hardcoded paths, configs and keys in here. the provided api keys in have expired and is of no use. so inorder to make it work, you have to do it yourselves.<br>
you might have to change almost all the hardcoded paths for this to work.<br>
