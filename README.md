# windlathe

`windlathe` provides experimental, pre-alpha utilities for defining and
validating metadata for multidimensional scientific model grids.

The current release validates versioned JSON manifests and provides structured
validation errors. The API and file format may change before version 1.0.

## Development environment

Create the Conda environment and activate it:

```console
conda env create -f environment.yml
conda activate windlathe
```

Run the tests with:

```console
pytest
```
