from myview.models import ADStaffSyncGroupup



class Command:

    def sync_ad_groups(self, *args, **options):
        from myview.models import ADStaffSyncGroupup
        ADStaffSyncGroupup.sync_ad_groups(None)
        print('done')
        return True



def run():
    command = Command()
    command.sync_ad_groups()
    print('done')

# if main 
if __name__ == "__main__":
    run()

