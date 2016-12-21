from tunicorn.app import Application

if __name__ == '__main__':
    Application('%(prog)s [OPTIONS] [APP_MODULE]').run()
