import sys
import os
import time
import multiprocessing
from PIL import Image

FLAG_DONE = None

FI_IMAGE_AMP = 15
FI_TILE_SIZE = 30
FI_TILE_FIT = 15
FI_TILE_FIT_RATIO = FI_TILE_SIZE / max(1, min(FI_TILE_SIZE, FI_TILE_FIT))
FI_TILE_FIT_SIZE = FI_TILE_SIZE / FI_TILE_FIT_RATIO

ORIGINAL_IMAGE_LARGE = None
ORIGINAL_IMAGE_SMALL = None
ORIGINAL_IMAGE_TILE_LARGE = []
ORIGINAL_IMAGE_TILE_SMALL = []
SOURCE_IMAGE_TILE_LARGE = []
SOURCE_IMAGE_TILE_SMALL = []
UNIQUE_ID = []


def source_image():
    global ORIGINAL_IMAGE_LARGE, ORIGINAL_IMAGE_SMALL

    img = Image.open("source.jpg")
    img_w = img.size[0]
    img_h = img.size[1]
    img = img.resize((img_w * FI_IMAGE_AMP, img_h * FI_IMAGE_AMP), Image.ANTIALIAS)
    img_amp_w = img.size[0]
    img_amp_h = img.size[1]

    print("%d %d" % (img_w, img_h))
    print("%d %d" % (img_amp_w, img_amp_h))

    img_crop_x = (img_amp_w % FI_TILE_SIZE) / 2
    img_crop_y = (img_amp_h % FI_TILE_SIZE) / 2
    img_crop_area = (
        img_crop_x,
        img_crop_y,
        img_amp_w - img_crop_x,
        img_amp_h - img_crop_y,
    )
    img_crop = img.crop(img_crop_area)
    img_crop_w = img_crop.size[0]
    img_crop_h = img_crop.size[1]
    ORIGINAL_IMAGE_LARGE = img_crop

    print("%d %d" % (img_crop_w, img_crop_h))

    img_fit = img_crop.resize(
        (int(img_crop_w / FI_TILE_FIT_RATIO), int(img_crop_h / FI_TILE_FIT_RATIO)),
        Image.ANTIALIAS,
    )
    img_fit_w = img_fit.size[0]
    img_fit_h = img_fit.size[1]
    ORIGINAL_IMAGE_SMALL = img_fit

    print("img fit %d %d" % (img_fit_w, img_fit_h))


def tile_image():
    global SOURCE_IMAGE_TILE_LARGE, SOURCE_IMAGE_TILE_SMALL

    # for root, subFolder, files in os.walk("source"):
    for root, subFolder, files in os.walk("images"):
        for filename in files:

            # TODO: multiprocessing here!

            print("Processing {:40.40}".format(filename), flush=True, end="\r")

            img = Image.open(os.path.join(root, filename))
            img_w = img.size[0]
            img_h = img.size[1]
            img_min = min(img_w, img_h)
            # print('%d %d %d' % (img_w, img_h, img_min))

            img_crop_x = (img_w % img_min) / 2
            img_crop_y = (img_h % img_min) / 2
            img_crop_area = (
                img_crop_x,
                img_crop_y,
                img_w - img_crop_x,
                img_h - img_crop_y,
            )
            img_crop = img.crop(img_crop_area)
            img_crop_w = img_crop.size[0]
            img_crop_h = img_crop.size[1]
            # print('%d %d' % (img_crop_w, img_crop_h))

            img_large = img_crop.resize(
                (int(FI_TILE_SIZE), int(FI_TILE_SIZE)), Image.ANTIALIAS
            )
            img_small = img_crop.resize(
                (int(FI_TILE_FIT_SIZE), int(FI_TILE_FIT_SIZE)), Image.ANTIALIAS
            )
            if img_large:
                SOURCE_IMAGE_TILE_LARGE.append(img_large)
                SOURCE_IMAGE_TILE_SMALL.append(img_small)

            # img_large.show()
            # img_small.show()
            # SOURCE_IMAGE_TILE_LARGE.append()
            # break
        # break
    print()
    print("Found %d tile(s)" % len(SOURCE_IMAGE_TILE_LARGE))


def build_image(queue_build, img_final, image_large):
    while True:
        large_tile_index, img_large_box = queue_build.get()
        if large_tile_index == FLAG_DONE:
            break
        img_final.paste(image_large[large_tile_index], img_large_box)

    img_final.save("ok.jpg")


def fit():
    global ORIGINAL_IMAGE_LARGE, ORIGINAL_IMAGE_SMALL, SOURCE_IMAGE_TILE_LARGE
    img_final = Image.new(ORIGINAL_IMAGE_LARGE.mode, ORIGINAL_IMAGE_LARGE.size)
    img_final_w = img_final.size[0]
    img_final_h = img_final.size[1]
    # calculate tile size
    tile_x_total = int(img_final_w / FI_TILE_SIZE)
    tile_y_total = int(img_final_h / FI_TILE_SIZE)
    tile_total = tile_x_total * tile_y_total

    print(
        "tile needed (x,y) (%d,%d) total: %d" % (tile_x_total, tile_y_total, tile_total)
    )

    CPU_COUNT = multiprocessing.cpu_count() - 1
    # TODO: SHOULD WE USE MULTITASKING?
    # OF COURSE
    find = multiprocessing.Queue(CPU_COUNT)
    build = multiprocessing.Queue()

    for i in range(CPU_COUNT):
        multiprocessing.Process(
            target=find_tile, args=(find, build, SOURCE_IMAGE_TILE_SMALL)
        ).start()
        print("Register find_process #%d" % i)
    multiprocessing.Process(
        target=build_image, args=(build, img_final, SOURCE_IMAGE_TILE_LARGE)
    ).start()
    print("Register build_process #1")

    progress = Progress(tile_total)
    for x in range(tile_x_total):
        for y in range(tile_y_total):
            box_large = (
                (x) * FI_TILE_SIZE,
                (y) * FI_TILE_SIZE,
                (x + 1) * FI_TILE_SIZE,
                (y + 1) * FI_TILE_SIZE,
            )
            box_small = (
                (x) * int(FI_TILE_FIT_SIZE),
                (y) * int(FI_TILE_FIT_SIZE),
                (x + 1) * int(FI_TILE_FIT_SIZE),
                (y + 1) * int(FI_TILE_FIT_SIZE),
            )
            find.put((list(ORIGINAL_IMAGE_SMALL.crop(box_small).getdata()), box_large))

            progress.update()

    find.put((FLAG_DONE, FLAG_DONE))


def find_tile(queue_find, queue_build, tiles_small):
    while True:
        img_small_data, img_large_box = queue_find.get(True)
        if img_small_data == FLAG_DONE:
            break
        # print(img_small_data)
        # print(img_large_box)
        deviation = sys.maxsize
        tile_i = 0
        tile_index = 0
        for tile in tiles_small:
            result = fit_compare(img_small_data, tile.getdata(), deviation)
            # print('[%d] %d' % (tile_i, result))
            if result < deviation and not (tile_index in UNIQUE_ID):
                deviation = result
                tile_index = tile_i
                UNIQUE_ID.append(tile_index)
            tile_i += 1

        # TODO: HERE IF YOU WANT TO BE UNIQUE TILE

        # print('result index: %d' % tile_index)
        queue_build.put((tile_index, img_large_box))
    queue_build.put((FLAG_DONE, FLAG_DONE))


def fit_compare(img_1, img_2, threshold):
    dev = 0
    for i in range(len(img_1)):
        dev += (
            ((img_1[i][0] - img_2[i][0]) ** 2)
            + ((img_1[i][1] - img_2[i][1]) ** 2)
            + ((img_1[i][2] - img_2[i][2]) ** 2)
        )
        if dev > threshold:
            break
    return dev


def eid_mubarak():
    source_image()
    tile_image()
    # THE HARDEST PART :(
    fit()


class Progress:
    def __init__(self, total):
        self.total = total
        self.count = 0

    def update(self):
        self.count += 1
        print(
            "Progress {:04.1f}% {}".format(
                self.count * 100 / self.total, UNIQUE_ID.count
            ),
            flush=True,
            end="\r",
        )


if __name__ == "__main__":
    eid_mubarak()
