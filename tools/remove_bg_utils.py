import base64
import json
import threading
import webbrowser
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image

Color = tuple[int, int, int]


def replace_background(image: Image.Image, source: Color, target: Color, tolerance: int) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = [
        (*target, alpha) if max(abs(red - source[0]), abs(green - source[1]), abs(blue - source[2])) <= tolerance else (red, green, blue, alpha)
        for red, green, blue, alpha in rgba.getdata()
    ]
    result = Image.new("RGBA", rgba.size)
    result.putdata(pixels)
    return result


def flatten_image(image: Image.Image, background: Color) -> Image.Image:
    rgba = image.convert("RGBA")
    flattened = Image.new("RGBA", rgba.size, (*background, 255))
    flattened.alpha_composite(rgba)
    return flattened.convert("RGB")


def save_image(image: Image.Image, path: Path, background: Color) -> None:
    image_format = format_for_extension(path.suffix)
    output = flatten_image(image, background) if image_format in {"JPEG", "MPO"} else image
    try:
        output.save(path, format=image_format)
    except OSError:
        if output.mode == "RGB":
            raise
        flatten_image(output, background).save(path, format=image_format)


def format_for_extension(extension: str) -> str:
    Image.init()
    image_format = Image.registered_extensions().get(extension.lower())
    if not image_format or image_format not in Image.SAVE:
        raise ValueError(f"Unsupported output format: {extension or '(none)'}")
    return image_format


def supported_extensions(writable: bool = False) -> list[str]:
    Image.init()
    registry = Image.SAVE if writable else Image.OPEN
    return sorted(extension for extension, image_format in Image.registered_extensions().items() if image_format in registry)


def encode_image(image: Image.Image, image_format: str, background: Color) -> bytes:
    output = flatten_image(image, background) if image_format in {"JPEG", "MPO"} else image
    buffer = BytesIO()
    try:
        output.save(buffer, format=image_format)
    except OSError:
        buffer = BytesIO()
        flatten_image(output, background).save(buffer, format=image_format)
    return buffer.getvalue()


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Background Color Replacer</title>
<style>
:root{font-family:system-ui,sans-serif;color:#eee;background:#171717}body{max-width:1100px;margin:auto;padding:24px}h1{font-size:22px}.controls{display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin-bottom:16px}label{display:grid;gap:5px;font-size:13px}button,input,select{font:inherit;padding:8px}button{cursor:pointer}canvas{display:block;max-width:100%;max-height:70vh;background:#333;cursor:crosshair}.status{min-height:24px;margin-top:10px;color:#bbb}.grow{flex:1;min-width:180px}
</style>
</head>
<body>
<h1>Background Color Replacer</h1>
<div class="controls">
<label class="grow">Image<input id="file" type="file"></label>
<label>New color<input id="target" type="color" value="#ffffff"></label>
<label>Tolerance <span id="amount">30</span><input id="tolerance" type="range" min="0" max="100" value="30"></label>
<label>Output format<select id="format"></select></label>
<button id="save" disabled>Save As</button>
</div>
<canvas id="canvas"></canvas>
<div id="status" class="status">Choose an image. The top-left pixel is selected as its background.</div>
<script>
const file=document.querySelector('#file'),target=document.querySelector('#target'),tolerance=document.querySelector('#tolerance'),amount=document.querySelector('#amount'),format=document.querySelector('#format'),save=document.querySelector('#save'),canvas=document.querySelector('#canvas'),status=document.querySelector('#status'),ctx=canvas.getContext('2d');
let originalData='',originalImage=null,source=[255,255,255],timer;
const rgb=h=>[parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];
const request=async(path,data)=>{const response=await fetch(path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):null});const result=await response.json();if(!response.ok)throw new Error(result.error);return result};
const draw=data=>new Promise(resolve=>{const image=new Image();image.onload=()=>{canvas.width=image.width;canvas.height=image.height;ctx.drawImage(image,0,0);resolve(image)};image.src='data:image/png;base64,'+data});
const process=async()=>{if(!originalData)return;status.textContent='Updating preview…';try{const result=await request('/process',{data:originalData,source,target:rgb(target.value),tolerance:+tolerance.value,format:'PNG'});await draw(result.data);status.textContent=`Background RGB(${source.join(', ')}) → ${target.value.toUpperCase()}`}catch(error){status.textContent=error.message}};
fetch('/formats').then(r=>r.json()).then(items=>items.forEach(([extension,name])=>format.add(new Option(`${extension} (${name})`,extension))));
file.onchange=async()=>{if(!file.files[0])return;status.textContent='Opening image…';const reader=new FileReader();reader.onload=async()=>{originalData=reader.result.split(',')[1];try{const result=await request('/load',{data:originalData});source=result.source;originalImage=await draw(result.data);save.disabled=false;await process()}catch(error){status.textContent=error.message}};reader.readAsDataURL(file.files[0])};
canvas.onclick=event=>{if(!originalImage)return;const box=canvas.getBoundingClientRect(),x=Math.min(canvas.width-1,Math.floor((event.clientX-box.left)*canvas.width/box.width)),y=Math.min(canvas.height-1,Math.floor((event.clientY-box.top)*canvas.height/box.height)),off=document.createElement('canvas');off.width=originalImage.width;off.height=originalImage.height;const offctx=off.getContext('2d');offctx.drawImage(originalImage,0,0);source=Array.from(offctx.getImageData(x,y,1,1).data.slice(0,3));process()};
tolerance.oninput=()=>{amount.textContent=tolerance.value;clearTimeout(timer);timer=setTimeout(process,150)};target.oninput=process;
save.onclick=async()=>{status.textContent='Preparing download…';try{const result=await request('/process',{data:originalData,source,target:rgb(target.value),tolerance:+tolerance.value,format:format.value});const link=document.createElement('a');link.href=`data:${result.mime};base64,${result.data}`;link.download=`background-replaced${result.extension}`;link.click();status.textContent='Saved'}catch(error){status.textContent=error.message}};
</script>
</body>
</html>"""


class AppHandler(BaseHTTPRequestHandler):
    def send_json(self, payload: object, status: int = 200) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/":
            data = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/formats":
            formats = [(extension, Image.registered_extensions()[extension]) for extension in supported_extensions(writable=True)]
            self.send_json(formats)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            with Image.open(BytesIO(base64.b64decode(payload["data"]))) as opened:
                image = opened.convert("RGBA")
            if self.path == "/load":
                data = encode_image(image, "PNG", (255, 255, 255))
                self.send_json({"data": base64.b64encode(data).decode(), "source": image.getpixel((0, 0))[:3]})
                return
            if self.path == "/process":
                extension = payload["format"]
                image_format = "PNG" if extension == "PNG" else format_for_extension(extension)
                target = tuple(payload["target"])
                result = replace_background(image, tuple(payload["source"]), target, int(payload["tolerance"]))
                data = encode_image(result, image_format, target)
                suffix = ".png" if extension == "PNG" else extension
                self.send_json({"data": base64.b64encode(data).decode(), "extension": suffix, "mime": Image.MIME.get(image_format, "application/octet-stream")})
                return
            self.send_error(404)
        except Exception as error:
            self.send_json({"error": str(error)}, 400)

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), AppHandler)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Background Color Replacer: {url}")
    print("Press Ctrl+C to stop.")
    threading.Timer(0.3, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
