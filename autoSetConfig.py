from paramiko import SSHClient
from paramiko import AutoAddPolicy
from paramiko import ssh_exception
from time import sleep
from os import mkdir
from os import path
from pandas import read_excel
from pandas import DataFrame
import yaml
from threading import Thread, BoundedSemaphore


def getYamlData(filepath: str):
    """
    获取yaml配置文件中的数据
    :param filepath: yaml配置文件路径
    :returns: yaml格式数据
    """
    with open(file=filepath, mode='r', encoding='utf-8') as file:
        data = file.read()
        result = yaml.load(data, Loader=yaml.FullLoader)
        return result


def getSheet(filepath: str):
    """
    获取execl文件中的数据
    :param filepath: execl文件路径
    :returns: execl中的所有数据，以DataFrame数据结构返回
    """
    return read_excel(filepath, sheet_name=0, converters={0: str}, names=['ip', 'uname', 'pwd'])


def runCommand(connect, command: str, timeout: int):
    """
    执行命令
    :param connect: sshClient创建的链接
    :param command: 需要在ssh链接中执行的命令
    :param timeout: 等待命令执行的时长
    :returns: 执行完命令的回显
    """
    connect.send(command + "\n")
    sleep(timeout)
    conf = connect.recv(65535).decode("utf8", "ignore")
    return conf


def save(filepath: str, data: any):
    """
    保存数据到文件中
    :param filepath: 文件的路径
    :param data: 要 保存的数据
    :returns: None
    """
    with open(file=filepath, mode="w+", encoding='utf-8') as file:
        file.write(data)


def checkSet(li1, li2, keyword):
    """
    获取配置
    :param li1: 用户配置
    :param li2: 默认配置
    :param keyword: 配置项
    :returns: 用户若没有配置则使用返回默认配置
    """
    return li1[keyword] if keyword in li1.keys() else li2[keyword]


def runningCommand(ssh, clist, run_set, key):
    """
    执行命令
    :param ssh: ssh配置
    :param clist: 命令列表
    :param run_set: 最终运行配置项
    :param key: 类型名字, 用以创建对应类型的文件夹及存放路径
    :returns: None
    """
    try:
        sshClient = SSHClient()
        sshClient.set_missing_host_key_policy(AutoAddPolicy())
        sshClient.connect(hostname=ssh['ip'], username=ssh['uname'],
                          password=ssh['pwd'], timeout=5)
    except TimeoutError:
        print("\033[0;31m[-]\033[0m" + '\tIP: ' + ssh['ip'] + ' 连接超时,已跳过')
        return
    except ConnectionResetError:
        print("\033[0;31m[-]\033[0m" + '\tIP: ' + ssh['ip'] + ' 连接被重置,已跳过')
        return
    except ssh_exception.AuthenticationException:
        print("\033[0;31m[-]\033[0m" + '\tIP: ' + ssh['ip'] + ' 身份验证失败,已跳过')
        return
    except:
        print("\033[0;31m[-]\033[0m" + '\tIP: ' + ssh['ip'] + ' 未知错误,已跳过')
        return
    connect = sshClient.invoke_shell()
    print("\033[0;32m[+]\033[0m" + '\t已连接至：' + ssh['ip'])
    for command in clist:
        print(ssh['ip'] + ' 正在执行: ' + command + ' 等待时间: ' + str(run_set['timeout']))
        r = runCommand(connect=connect, command=command, timeout=run_set['timeout'])
        if run_set['saved']:
            save('./config/' + key + '/' + ssh['ip'] + '.txt', "# command: " + command + "\n" + r + "\n")
    sshClient.close()


def start(yamlPath: str, execlPath: str):
    """
    启动函数
    :param yamlPath: yaml配置文件路径
    :param execlPath: execl文件路径
    :returns: None
    """
    threadLimiter = BoundedSemaphore(5)
    default = {
        'timeout': 10,
        'saved': True
    }
    run_set = default

    config = getYamlData(yamlPath)
    login_setting = getSheet(execlPath)
    data = login_setting.to_dict()
    index_list = list(login_setting['ip'].to_dict().values())

    for key, values in config.items():
        if 'host' not in values.keys():
            print(key + ' 主机配置获取错误或不存在，已跳过')
            continue
        elif 'command' not in values.keys():
            print(key + ' 命令配置获取错误或不存在，已跳过')
            continue

        if not path.exists('./config/' + key):
            mkdir('./config/' + key)

        for keyword in default.keys():
            run_set[keyword] = checkSet(values, default, keyword)

        for host in values['host']:
            if host in index_list:
                index = index_list.index(host)
                # print(data['ip'][index])
                # print(data['uname'][index])
                # print(data['pwd'][index])

                threadLimiter.acquire()
                try:
                    Thread(target=runningCommand, args=[
                        {
                            'ip': data['ip'][index],
                            'uname': data['uname'][index],
                            'pwd': data['pwd'][index]
                        },
                        values['command'],
                        run_set,
                        key,
                    ]).start()
                finally:
                    threadLimiter.release()
            else:
                print("\033[0;31m[-]\033[0m" + '\t在execl中未找到ip为 ' + host + ' 的主机')


def main():
    run = True
    if not path.exists('config.xlsx'):
        pd1 = DataFrame(columns=['IP', '用户名', '密码'])
        pd1.to_excel('config.xlsx', index=False)
        print("已生成配置文件 config.xlsx，填写设备配置到execl后，再次运行本程序！")
        run = False

    if not path.exists('config.yaml'):
        with open(file='config.yaml', mode='w+', encoding='utf-8'):
            pass
        print("已生成配置文件 config.yaml，参考 https://github.com/cvic131/autoSetConfig 进行配置后，再次运行本程序！")
        run = False

    if run:
        if not path.exists('config'):
            mkdir('config')

        start('config.yaml', 'config.xlsx')


if __name__ == '__main__':
    main()