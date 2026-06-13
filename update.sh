#!/bin/bash
cd ~/Goldpan
python3 fetch_dishes.py
git add dishes.json
git commit -m "Update dishes"
git push
