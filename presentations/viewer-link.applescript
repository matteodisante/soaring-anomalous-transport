-- Fixed-purpose URL handler. URL contents are never executed as shell commands.
on launchViewer()
    set applicationPath to POSIX path of (path to me)
    set talkDirectory to do shell script "/usr/bin/dirname " & quoted form of applicationPath
    set launcherPath to talkDirectory & "/launch_viewer.command"
    do shell script "/bin/bash " & quoted form of launcherPath & " >/dev/null 2>&1 &"
end launchViewer

on open location requestedURL
    if requestedURL is "soaring-viewer://open" or requestedURL is "soaring-viewer://open/" then
        launchViewer()
    end if
end open location

on run
    launchViewer()
end run
