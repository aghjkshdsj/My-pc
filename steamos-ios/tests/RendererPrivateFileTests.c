/* Hosted native Darwin tests of the actual patched upstream allocator.
 * No iPhone GPU, Linux boot or Metal claim follows from these tests. */
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include "anon_file.h"

static void empty_directory(const char *path) {
   DIR *dir = opendir(path); assert(dir);
   struct dirent *entry;
   while ((entry = readdir(dir))) assert(!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."));
   assert(closedir(dir) == 0);
}

int main(void) {
   const char *temp = getenv("TMPDIR"); assert(temp && temp[0] == '/');
   char directory[4096], alias[4096];
   assert(snprintf(directory, sizeof(directory), "%s/mpc-private-tests-XXXXXX", temp) < (int)sizeof(directory));
   assert(mkdtemp(directory)); assert(chmod(directory, 0700) == 0);
   assert(setenv("MPC_GPU_SHM_DIR", directory, 1) == 0);
   const size_t sizes[] = {256, 16384, 3686400, 16 * 1024 * 1024};
   for (unsigned int i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i) {
      size_t size = sizes[i]; int fd = os_create_anonymous_file((off_t)size, "hosted-test"); assert(fd >= 0);
      struct stat st; assert(fstat(fd, &st) == 0 && S_ISREG(st.st_mode));
      assert(st.st_size == (off_t)size && st.st_nlink == 0 && (st.st_mode & 0777) == 0600);
      assert(fcntl(fd, F_GETFD) & FD_CLOEXEC); empty_directory(directory);
      int duplicate = fcntl(fd, F_DUPFD_CLOEXEC, 3); assert(duplicate >= 0);
      unsigned char *a = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
      unsigned char *b = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, duplicate, 0);
      assert(a != MAP_FAILED && b != MAP_FAILED && a != b);
      assert(close(fd) == 0 && close(duplicate) == 0);
      a[0] = 0x35; a[size - 1] = 0x79; assert(b[0] == 0x35 && b[size - 1] == 0x79);
      b[size / 2] = 0xb4; assert(a[size / 2] == 0xb4);
      assert(munmap(a, size) == 0 && munmap(b, size) == 0);
   }
   assert(os_create_anonymous_file(-1, "invalid-size") < 0 && errno == EINVAL); empty_directory(directory);
   assert(chmod(directory, 0755) == 0);
   assert(os_create_anonymous_file(256, "nonprivate") < 0 && errno == EACCES);
   assert(chmod(directory, 0700) == 0);
   assert(snprintf(alias, sizeof(alias), "%s-symlink", directory) < (int)sizeof(alias));
   assert(symlink(directory, alias) == 0); assert(setenv("MPC_GPU_SHM_DIR", alias, 1) == 0);
   assert(os_create_anonymous_file(256, "symlink") < 0); assert(unlink(alias) == 0);
   assert(setenv("MPC_GPU_SHM_DIR", "/mpc-deliberately-missing-test-dir", 1) == 0);
   assert(os_create_anonymous_file(256, "missing") < 0);
   assert(setenv("MPC_GPU_SHM_DIR", "relative", 1) == 0);
   assert(os_create_anonymous_file(256, "relative") < 0 && errno == EINVAL);
   empty_directory(directory); assert(rmdir(directory) == 0);
   puts("PRIVATE_FILE_TESTS_PASSED scope=native-darwin-allocator-only shared-alias=passed cloexec=passed unlinked=passed failure-rejection=passed");
   return 0;
}
