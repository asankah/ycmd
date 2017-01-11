#if defined(FOO)
int value = 0;
#else
int value = 1;
#endif

void func() {
  // value occupies columns 3-7 on line 9.
  value += 1;
}
