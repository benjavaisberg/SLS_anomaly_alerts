try:
    import private_config as p_conf
except ModuleNotFoundError:
    print("No private_config found!")
    print("Fill out private_config_example.py and copy it to private_config.py")
    print("DO NOT ADD YOUR PRIVATE_CONFIG TO VERSION CONTROL")
import config as conf
import yagmail

def send_daily():
    with yagmail.SMTP(p_conf.USERNAME, p_conf.PASSWORD) as sender:
        params = {}
        params["to"] = p_conf.TO_LIST
        sender.send(**params)

if __name__ == "__main__":
    send_daily()