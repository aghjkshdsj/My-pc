/* Fresh MIT helper for an app-owned, unnamed renderer communication file.
 * This provides an fd and lifetime semantics, not Metal memory import. */
#ifndef MPC_PRIVATE_SHARED_FILE_H
#define MPC_PRIVATE_SHARED_FILE_H
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>

static int mpc_ios_private_file_open(const char *directory)
{
   if (!directory || directory[0] != '/') { errno = EINVAL; return -1; }
   int dir = open(directory, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
   if (dir < 0) return -1;
   struct stat info;
   if (fstat(dir, &info) != 0) {
      int saved = errno; close(dir); errno = saved; return -1;
   }
   if (!S_ISDIR(info.st_mode) || info.st_uid != geteuid() ||
       (info.st_mode & 0777) != 0700) {
      close(dir); errno = EACCES; return -1;
   }
   int fd = -1;
   for (unsigned int attempt = 0; attempt < 32; ++attempt) {
      char name[64];
      snprintf(name, sizeof(name), "mpc-gpu-%08x-%08x", arc4random(), attempt);
      fd = openat(dir, name, O_RDWR | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
      if (fd < 0) { if (errno == EEXIST) continue; break; }
      if (unlinkat(dir, name, 0) != 0) {
         int saved = errno; close(fd); fd = -1; errno = saved;
      }
      break;
   }
   int saved = errno;
   close(dir);
   errno = saved;
   return fd;
}
#endif
