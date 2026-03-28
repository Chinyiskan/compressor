import subprocess
import imageio_ffmpeg
exe = imageio_ffmpeg.get_ffmpeg_exe()
cmd = [exe, "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:r=1:d=1", "-vf", "scale='trunc(iw*min(1,min(1280/iw,1280/ih))/2)*2':-2", "-vframes", "1", "-y", "out.jpg"]
print("Running:", cmd)
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
print(res.stderr)
