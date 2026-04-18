# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial public API: `wrap`, `ComponentWrapper`, `is_wrapped`,
  `register_proxy_defaults`, `make_wrapper_class`.
- Built-in proxy-prop defaults for `dcc.Graph`, `dash_table.DataTable`,
  `dcc.Input`, `dcc.Dropdown`, `dcc.Textarea`, `dcc.Slider`,
  `dcc.RangeSlider`, `dcc.DatePickerSingle`, `dcc.DatePickerRange`.
- First-class nested-wrapper support (arbitrary depth).
