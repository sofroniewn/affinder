import sys
from enum import Enum
import toolz as tz
from magicgui import magicgui
import napari
from skimage.transform import (
    AffineTransform,
    EuclideanTransform,
    SimilarityTransform,
)


class AffineTransformChoices(Enum):
    affine=AffineTransform
    Euclidean=EuclideanTransform
    similarity=SimilarityTransform

@tz.curry
def next_layer_callback(
        value,  # we ignore the arguments returned with the event -- we will
        *args,  # instead introspect the layer data and selection state
        viewer,
        reference_image_layer,
        reference_points_layer,
        moving_image_layer,
        moving_points_layer,
        model_class,
        ):
    pts0, pts1 = reference_points_layer.data, moving_points_layer.data
    n0, n1 = len(pts0), len(pts1)
    ndim = pts0.shape[1]
    if reference_points_layer.selected:
        if n0 < ndim + 1:
            return
        if n0 > n1:
            reference_points_layer.selected = False
            moving_points_layer.selected = True
            viewer.layers.move(viewer.layers.index(moving_image_layer), -1)
            viewer.layers.move(viewer.layers.index(moving_points_layer), -1)
            moving_points_layer.mode = 'add'
    elif moving_points_layer.selected:
        if n1 == n0:
            # we just added enough points:
            # estimate transform, go back to layer0
            if n0 > ndim:
                mat = calculate_transform(pts0, pts1, model_class=model_class)
                moving_image_layer.affine = (
                        reference_image_layer.affine.affine_matrix @ mat.params
                        )
                moving_points_layer.affine = (
                        reference_image_layer.affine.affine_matrix @ mat.params
                        )
            reference_points_layer.selected = True
            moving_points_layer.selected = False
            reference_points_layer.mode = 'add'
            viewer.layers.move(viewer.layers.index(reference_image_layer), -1)
            viewer.layers.move(viewer.layers.index(reference_points_layer), -1)
        

# make a bindable function to shut things down
@magicgui
def close_affinder(layers, callback):
    for layer in layers:
        layer.events.data.disconnect(callback)
        layer.mode = 'pan_zoom'


@magicgui(
        call_button='Start',
        layout='vertical',
        viewer={'visible': False, 'label': ' '},
        )
def start_affinder(
        reference: napari.layers.Image,
        moving: napari.layers.Image,
        model: AffineTransformChoices,
        viewer : napari.Viewer,
        ):
    mode = start_affinder._call_button.text  # can be "Start" or "Finish"

    if mode == 'Start':
        # make a points layer for each image
        points_layers = []
        # Use C0 and C1 from matplotlib color cycle
        for layer, color in [
                (reference, (0.122, 0.467, 0.706, 1.0)),
                (moving, (1.0, 0.498, 0.055, 1.0)),
                ]:
            new_layer = napari.layers.Points(
                    ndim=layer.ndim, name=layer.name + '_pts', affine=layer.affine
                    )
            new_layer.current_face_color = color
            viewer.layers.append(new_layer)
            points_layers.append(new_layer)
        pts_layer0 = points_layers[0]
        pts_layer1 = points_layers[1]

        # make a callback for points added
        callback = next_layer_callback(
            viewer=viewer,
            reference_image_layer=reference,
            reference_points_layer=pts_layer0,
            moving_image_layer=moving,
            moving_points_layer=pts_layer1,
            model_class=model.value,
            )
        pts_layer0.events.data.connect(callback)
        pts_layer1.events.data.connect(callback)

        # get the layer order started
        for layer in [moving, pts_layer1, reference, pts_layer0]:
            viewer.layers.move(viewer.layers.index(layer), -1)

        viewer.layers.unselect_all()
        pts_layer0.selected = True
        pts_layer0.mode = 'add'

        close_affinder.layers.bind(points_layers)
        close_affinder.callback.bind(callback)

        # change the button/mode for next run
        start_affinder._call_button.text = 'Finish'
    else:  # we are in Finish mode
        close_affinder()
        start_affinder._call_button.text = 'Start'


def calculate_transform(src, dst, model_class=AffineTransform):
    """Calculate transformation matrix from matched coordinate pairs.

    Parameters
    ----------
    src : ndarray
        Matched row, column coordinates from source image.
    dst : ndarray
        Matched row, column coordinates from destination image.
    model_class : scikit-image transformation class, optional.
        By default, model=AffineTransform().

    Returns
    -------
    transform
        scikit-image Transformation object
    """
    model = model_class()
    model.estimate(dst, src)  # we want the inverse
    return model


def main():
    fns = sys.argv[1:]
    viewer = napari.Viewer()
    if len(fns) > 0:
        viewer.open(fns, stack=False)
    viewer.window.add_dock_widget(start_affinder, area='right')
    napari.run()


if __name__ == '__main__':
    main()
