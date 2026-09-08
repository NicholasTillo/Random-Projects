from PIL import Image

from pixelate import pixelate


def test():
    img = Image.new("RGB", (100, 60))
    for x in range(100):
        for y in range(60):
            img.putpixel((x, y), (x * 2, y * 4, 128))

    small = pixelate(img, 10, 256)
    assert small.size == (10, 6), small.size

    # block averaging, not point sampling: top-left block is the mean of x=0..9
    assert small.getpixel((0, 0))[0] == 9, small.getpixel((0, 0))

    assert len(set(pixelate(img, 4, 8).getdata())) <= 8
    assert pixelate(img, 1000, 256).size == (1, 1)      # block bigger than image
    assert pixelate(img, 8, 256).size == (12, 7)        # floor division
    print("ok")


if __name__ == "__main__":
    test()
