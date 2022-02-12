docker run --rm -it --entrypoint bash \
  --volume=${PWD}/submission:/autograder/submission:rw \
  --volume=${PWD}/results:/autograder/results:rw \
  proj2-grader:student
