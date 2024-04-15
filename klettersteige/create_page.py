import datetime
import json
import warnings
from io import BytesIO

import geopandas as gpd
import gpxo
import matplotlib.pyplot as plt
import pandas as pd
import pyshorteners
import qrcode
import requests
import seaborn as sns
from jinja2 import Environment, FileSystemLoader
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image, ImageChops
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from shapely.geometry import Point

warnings.filterwarnings("ignore")

with open("data/klettersteige.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    data = pd.DataFrame(data).T

options = {
    "page-width": "11.693in",
    "page-height": "8.267in",
    "dpi": 300,  # Setting the DPI to ensure high-quality output
}

env = Environment(loader=FileSystemLoader("."))
template = env.get_template("data/template.html")

diffs = {"B": 1, "B/C": 2, "C": 2, "C/D": 3, "D": 3, "D/E": 4, "E": 4, "E/F": 5, "F": 5}

def get_gpx(row):
    gpxo_file = row["gpx"]
    r = requests.get(gpxo_file)
    with open("temp/temp.gpx", "wb") as f:
        f.write(r.content)
    return gpxo.Track("temp/temp.gpx")


def create_map(row):
    austria = gpd.read_file("data/austria-with-regions_.geojson")

    gpxo_data = get_gpx(row)

    poi = Point(gpxo_data.longitude[0], gpxo_data.latitude[0])
    austria["distance"] = austria.geometry.distance(poi)

    fig, ax = plt.subplots(figsize=(10, 6.1), dpi=300)
    austria.boundary.plot(ax=ax, color="#333333", linewidth=0.8)
    austria[austria["distance"] == austria["distance"].min()].plot(
        ax=ax, color="#dddddd"
    )

    url = "https://img.icons8.com/ios-filled/10000/000000/marker.png"
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))

    imagebox = OffsetImage(img, zoom=0.025)
    ab = AnnotationBbox(
        imagebox,
        (gpxo_data.longitude[0], gpxo_data.latitude[0]),
        frameon=False,
        bboxprops={"edgecolor": "none"},
        pad=0,
        box_alignment=(0.5, 0),
    )
    ax.add_artist(ab)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    plt.savefig("out/map.png")


def create_qr_code(row):
    # get index
    Logo_link = "https://i.etsystatic.com/36665707/r/il/3150e0/4563618978/il_1140xN.4563618978_6ylt.jpg"
    response = requests.get(Logo_link)
    logo = Image.open(BytesIO(response.content))

    # Resize logo image
    basewidth = 100
    wpercent = basewidth / float(logo.size[0])
    hsize = int((float(logo.size[1]) * wpercent))
    logo = logo.resize((basewidth, hsize), Image.Resampling.LANCZOS)

    # Configure QR code
    QRcode = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=0,  # Remove white border by setting it to 0
    )

    # URL to be encoded in the QR code
    url = row.name
    short_url = pyshorteners.Shortener().tinyurl.short(url)
    QRcode.add_data(short_url)
    QRcode.make()

    # Set QR code color
    QRcolor = "Black"
    QRimg = QRcode.make_image(fill_color=QRcolor, back_color="white").convert("RGB")

    # Position to paste the logo image
    pos = ((QRimg.size[0] - logo.size[0]) // 2, (QRimg.size[1] - logo.size[1]) // 2)
    QRimg.paste(logo, pos)

    # Save the QR code generated
    QRimg.save("out/qr.png")


def download_topo(row):
    # download topo
    r = requests.get(row["topo_url"])
    img = Image.open(BytesIO(r.content))

    # if its wider than high, rotate it by 90 degrees
    if img.size[0] > img.size[1]:
        img = img.rotate(90, expand=True)

    # resize to width 2000
    basewidth = 2000
    wpercent = basewidth / float(img.size[0])
    hsize = int((float(img.size[1]) * wpercent))
    img = img.resize((basewidth, hsize), Image.Resampling.LANCZOS)

    # remove white borders
    img = trim(img)

    # save
    img.save("out/topo.jpg")


def trim(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)


def create_page(row):
    jinja_data = {
        "titel": row["titel"].upper(),
        "climbing_time": datetime.datetime.strptime(
            row["kletterzeit"], "%H:%M:%S"
        ).strftime("%H:%M"),
        "ascent_time": datetime.datetime.strptime(row["zustieg"], "%H:%M:%S").strftime(
            "%H:%M"
        ),
        "descent_time": datetime.datetime.strptime(row["abstieg"], "%H:%M:%S").strftime(
            "%H:%M"
        ),
        "total_height": row["gesamthöhe"],
        "starting_height": row["ausgangspunkt_höhe"],
        "region": row["region"],
        "difficulty": diffs[row["schwierigkeit"]],
        "scenery": int(row["Landschaft:"]),
        "strength": int(row["Kraft:"]),
        "condition": int(row["Kondition:"]),
        "months": [
            {"name": "JAN", "selected": "Jan" in row["Beste Jahreszeit:"]},
            {"name": "FEB", "selected": "Feb" in row["Beste Jahreszeit:"]},
            {"name": "MÄR", "selected": "Mär" in row["Beste Jahreszeit:"]},
            {"name": "APR", "selected": "Apr" in row["Beste Jahreszeit:"]},
            {"name": "MAI", "selected": "Mai" in row["Beste Jahreszeit:"]},
            {"name": "JUN", "selected": "Jun" in row["Beste Jahreszeit:"]},
            {"name": "JUL", "selected": "Jul" in row["Beste Jahreszeit:"]},
            {"name": "AUG", "selected": "Aug" in row["Beste Jahreszeit:"]},
            {"name": "SEP", "selected": "Sep" in row["Beste Jahreszeit:"]},
            {"name": "OKT", "selected": "Okt" in row["Beste Jahreszeit:"]},
            {"name": "NOV", "selected": "Nov" in row["Beste Jahreszeit:"]},
            {"name": "DEC", "selected": "Dez" in row["Beste Jahreszeit:"]},
        ],
        "image_url_1": row["img0"],
        "image_url_2": row["img1"],
        "image_url_3": row["img2"]
    }

    # render template with data
    html = template.render(jinja_data)

    # save
    with open("out/output.html", "w", encoding="utf-8") as f:
        f.write(html)


def screenshot_page():
    options = Options()
    options.headless = True  # Enable headless mode if you don't need a GUI
    driver = webdriver.Chrome(options=options)
    driver.get(
        "file:///home/moritz/private/klettersteige/out/output.html"
    )  # Update with the absolute path
    driver.set_window_size(3508, 2650)
    # wait 1 second for the page to load
    driver.implicitly_wait(1)
    driver.save_screenshot("out/output.png")
    driver.quit()


print(len(data))

if __name__ == "__main__":
    row = data.iloc[13]
    create_map(row)
    create_qr_code(row)
    download_topo(row)
    create_page(row)
    screenshot_page()
