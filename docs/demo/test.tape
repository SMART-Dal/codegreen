# CodeGreen Terminal Demo - Fine-Grained Energy Profiling

Output test.mp4
Output test.gif

Require echo

# Authentic terminal with Darkside theme
Set Shell "bash"
Set FontSize 16
Set Width 1400
Set Height 900
Set Padding 30
Set Theme "Darkside"
Set Framerate 60
Set PlaybackSpeed 1
Set TypingSpeed 20ms
Set Margin 10
Set MarginFill "#4dae50"
Set BorderRadius 10
Set WindowBar Colorful






# Type@20ms "git clone https://github.com/codegreen/codegreen.git" Enter
# Sleep 2s
Type@20ms "cd ~/codegreen" Enter
Sleep 1.5s
Type@20ms "./install.sh" Enter
# Wait+Screen@240s /"Docs:"/
Sleep 20s

Type "" Enter
Sleep 1.5s

Type@20ms "# After installation, run initialize sensors command with sudo permissions" Enter
Sleep 3s
Type@20ms "codegreen init-sensors" Enter
Sleep 1s
# Wait /"codegreen info"/
Sleep 10s
