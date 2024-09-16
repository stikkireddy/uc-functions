TOP_DIR := .
SRC_DIR := $(TOP_DIR)/uc_functions
DIST_DIR := $(TOP_DIR)/dist
TEST_DIR := $(TOP_DIR)/tests
REPORT_DIR := $(TEST_DIR)/coverage_report

# commands
PYTEST := pytest -s -n auto
BLACK := black --line-length 88
ISORT := isort --profile black --line-length 88

build:
	@echo "Cleaning build..."
	@rm -rf dist build
	@echo "Cleaned dist and build..."
	@echo "Building wheel..."
	@pip install wheel
	@echo "Build finished..."
	@echo "Making distributions..."
	@python setup.py bdist_wheel sdist
	@echo "Finished making distributions..."

upload:
	@echo "Uploading to PyPI..."
	@twine upload dist/*
	@echo "Finished uploading to PyPI..."

test:
	@echo "Running unit tests..."
	@$(PYTEST) --cov-report term --cov-report html:$(REPORT_DIR) --cov=$(SRC_DIR) $(TEST_DIR)
	@echo "Finished unit unit tests."

fmt:
	@echo "Formatting code..."
	@$(ISORT) $(SRC_DIR) $(TEST_DIR)
	@$(BLACK) $(SRC_DIR) $(TEST_DIR)
	@echo "Finished formatting code."

.PHONY: build pytest upload test