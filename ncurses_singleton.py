# import curses


# class NCursesSingleton:
#     _instance = None

#     def __new__(cls, stdscr=None):
#         if cls._instance is None:
#             cls._instance = super(NCursesSingleton, cls).__new__(cls)
#             cls._instance.stdscr = stdscr
#         return cls._instance
