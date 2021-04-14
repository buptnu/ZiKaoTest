#-*- coding: utf-8 -*-

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import timedelta, date, datetime

from flask import current_app
import os, sys, random, logging

app = Flask(__name__)
login_manager = LoginManager(app)
login_manager.login_view = '/index.html'

# app.secret_key = os.urandom(24)
app.secret_key = "ajdfskl;asdlfkiory09346jlaigr"

app.permanent_session_lifetime = timedelta(minutes=120)

if sys.platform.startswith('win'):
    dbfile_prefix = 'sqlite:///'
else:  # 否则使用四个斜线
    dbfile_prefix = 'sqlite:////'

app.config['SQLALCHEMY_DATABASE_URI'] = dbfile_prefix + os.path.join(app.root_path, 'ZiKao.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

date_lable = date.today().strftime("%Y%m%d")


app.config['UPLOAD_FOLDER'] = 'upload/' + date_lable
db = SQLAlchemy(app)

db_table_name = "users" + date_lable



# add handler and formatter to logger
LOGFORMAT = "%(asctime)-15s %(levelname)s %(filename)s %(lineno)d %(process)d %(message)s"
DATEFORMAT = "%a %d %b %Y %H:%M:%S"
formatter = logging.Formatter(LOGFORMAT, DATEFORMAT)

handler = logging.FileHandler('flask.log')
handler.setFormatter(formatter)
handler.setLevel(logging.NOTSET)

app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)
app.logger.info('===================================================')


class User(db.Model, UserMixin):
#    __tablename__ = "users20210328"
    __tablename__ = db_table_name

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    num = db.Column(db.String(20), unique=True)
    exam_seq = db.Column(db.INT)
    login_time = db.Column(db.DateTime)
    logout_time = db.Column(db.DateTime)
    file_uploaded = db.Column(db.DateTime)

class InputUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    num = db.Column(db.String(20), unique=True)

db.create_all()

@app.template_filter('formatdatetime')
def format_datetime(dt,format="%Y-%m-%d %H:%M:%S"):
    if dt is None:
        return ""
    else:
        return dt.strftime(format)

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.errorhandler(404)
def page_not_found(e):
    if current_user.is_authenticated:
        logout_user()
    return render_template('errors/404.html'), 404

@app.errorhandler(400)
def page_not_found(e):
    if current_user.is_authenticated:
        logout_user()
    return render_template('errors/400.html'), 400

@app.route('/',methods=['GET','POST'])
def index():
    if request.method == 'GET':
        if current_user.is_authenticated:
            logout_user()
        return render_template('index.html')

    username = str(request.values.get('username')).strip()
    usernum = str(request.values.get('usernum')).strip()
    iuser = InputUser.query.filter(InputUser.num == usernum, InputUser.name == username).first()

    if iuser is not None:
        user = User.query.filter(User.num == usernum).first()
        if user is not None:  # 登陆过
            login_user(user)
            if user.logout_time:
                logout_user()
                flash("你已经完成了本次操作考核，请离开考场！")
                return redirect(url_for('logout'))
            else:
                flash("考试中。。。。。")
                return redirect(url_for('show_exam'))
        else:
            user = User()
            user.name = username
            user.num = usernum

            user.login_time = datetime.now()

            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash("请开始考试。。。")
            return redirect(url_for('show_exam'))
    else:
        flash("请输入准确的姓名和准考证号码！仍然有问题，请咨询现场监考教师")
        return redirect(url_for('index'))

@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('index'))

@app.route('/examinfo')
def exam_info():
    now = datetime.now()
    exam_time = 120 #显示120分钟内的记录
    exam_count = 80 #每场考试最多40人,两个考场
    users = User.query.filter(User.login_time > now - timedelta(minutes=exam_time)) \
       .order_by(User.file_uploaded.desc()).limit(exam_count).all()
    return render_template('examinfo.html', users=users)

@app.route('/show_note')
@login_required
def show_note():
    flash("请严格按照要求进行考核操作")
    return render_template('note.html')


@app.route('/show_exam')
@login_required
def show_exam():
    flash("请认真阅读理解题目，顺序完成操作,并把过程记录到上传文档中")
    return render_template('exampaper.html', te=get_exam_paper())

# 抽选考题目录下的文件，0号是没有考题的情况
def get_exam_paper():
    fs = [f for f in os.listdir(os.path.join(os.getcwd(), "static/exam")) if f.endswith('.jpg')]
    n = len(fs)
    fs.sort()
    i = random.randint(1, n - 1)

    if current_user.exam_seq is None:  # 还没有分配考题
        current_user.exam_seq = i
        db.session.commit()
    else:
        i = current_user.exam_seq

    if (n > 1):
        the_exam = "/static/exam/" + str(fs[i])
    else:
        the_exam = "/static/exam/0.jpg"
    return the_exam

# 设置允许上传的文件类型
ALLOWED_EXTENSIONS = {'doc', 'docx'}  # , 'txt', 'png', 'jpg'}

# 检查文件类型是否合法
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST', 'GET'])
@login_required
def upload():
    if request.method == 'GET':
        flash("请准确选择记录操作和结果的文档，并提交")
        return render_template('upload.html')

    #    else:# request.method == 'POST':
    f = request.files['file']

    app.logger.info(current_user.name + "=" + f.filename)

    if f and allowed_file(f.filename):
        save_dir = os.path.join(os.getcwd(), app.config['UPLOAD_FOLDER'])
        #        save_dir = unicode(save_dir,'GB2312')
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)
        if os.path.exists(save_dir + f.filename):
            os.remove(save_dir, f)
        f.save(os.path.join(save_dir, \
                            current_user.name + '_' + \
                            current_user.num + '_' + \
                            f.filename))
        current_user.file_uploaded = datetime.now()
        db.session.commit()
        flash("文件提交成功，可以退出考试")
        return redirect(url_for('logout'))
    else:
        flash("文件提交失败，请再次尝试，或者联系监考老师")
        return render_template('upload.html')


@app.route('/logout')
def logout():
    current_user.logout_time = datetime.now()
    db.session.commit()
    session.pop('username', None)
    session.pop('usernum', None)
    logout_user()
    flash("考试结束，请：1、关闭计算机   2、带上自己物品安静离开。")
    return render_template('logout.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
