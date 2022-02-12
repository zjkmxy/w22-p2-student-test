# CS118 Project 2 Autograder (For Student use)

## How to use the autograder
1. Copy your tarball `XXX_YYY_ZZZ.tar.gz` into `submission` folder.
2. Run the shell command

```bash
docker run --rm -it \
  --volume=${PWD}/submission:/autograder/submission:rw \
  --volume=${PWD}/results:/autograder/results:rw \
  ghcr.io/zjkmxy/w22-p2-student-test:latest
```

* The last command may take very long (> 5 min)
