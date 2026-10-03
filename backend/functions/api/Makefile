.PHONY: build-VidaApiFunction

build-VidaApiFunction:
	mkdir -p $(ARTIFACTS_DIR)/shared
	mkdir -p $(ARTIFACTS_DIR)/routes
	cp -r $(CURDIR)/shared/* $(ARTIFACTS_DIR)/shared/
	cp -r $(CURDIR)/api/routes/* $(ARTIFACTS_DIR)/routes/
	cp $(CURDIR)/shared/__init__.py $(ARTIFACTS_DIR)/shared/__init__.py
	cp $(CURDIR)/api/handler.py $(ARTIFACTS_DIR)/handler.py
	pip install -r $(CURDIR)/api/requirements.txt -t $(ARTIFACTS_DIR)/ --quiet
