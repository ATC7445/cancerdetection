from flask import Flask, render_template, request, redirect,jsonify 
import os 
from ultralytics import YOLO 
from PIL import Image
import glob
from flask_mysqldb import MySQL
from datetime import datetime
from waitress import serve

app = Flask(__name__)

app.secret_key = "your_secret_key"

# ตั้งค่า MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'img_db'

mysql = MySQL(app)

# กำหนด path สำหรับเก็บรูปภาพ
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # จำกัดขนาดไฟล์สูงสุดที่ 16MB

# กำหนด path สำหรับโฟลเดอร์ result
RESULT_FOLDER = 'static/result'
app.config['RESULT_FOLDER'] = RESULT_FOLDER

# ตรวจสอบว่ามีโฟลเดอร์สำหรับเก็บผลลัพธ์หรือไม่ ถ้าไม่มีให้สร้างขึ้นมา
if not os.path.exists(RESULT_FOLDER):
    os.makedirs(RESULT_FOLDER)
# ตรวจสอบว่ามีโฟลเดอร์สำหรับเก็บรูปภาพหรือไม่ ถ้าไม่มีให้สร้างขึ้นมา
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Route สำหรับหน้า index
@app.route('/')
def index():
    return render_template('index.html')
# Route สำหรับหน้า imgClass สำหรับทำนายแบบ image classification
@app.route('/obj2')
def obj2():
    return render_template('obj2.html')

#ฟังชันส์สำหรับ save รูปภาพที่ predict
@app.route('/save_result', methods=['POST'])
def save_result():
    image_name = request.json.get('image_name')  # รับชื่อไฟล์จาก JSON
    if image_name:
        file_path = os.path.join(app.config['RESULT_FOLDER'], image_name)

        if os.path.exists(file_path):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # บันทึกลงฐานข้อมูล
            cur = mysql.connection.cursor()
            query = "INSERT INTO images (name, path, upload_time) VALUES (%s, %s, %s)"
            cur.execute(query, (image_name, file_path, timestamp))
            mysql.connection.commit()
            cur.close()

            return jsonify({"success": True, "message": "Save successful!"}), 200
        else:
            return jsonify({"success": False, "message": "File does not exist."}), 400

    return jsonify({"success": False, "message": "No file name provided."}), 400

# ฟังก์ชันสำหรับอัปโหลดรูปภาพ
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:  # ตรวจสอบว่ามี key 'file' หรือไม่
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':  # ตรวจสอบว่ามีการเลือกไฟล์
        return redirect(request.url)

    if file:
        filename = file.filename  # ดึงชื่อไฟล์
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # บันทึกไฟล์ไปยังตำแหน่งที่กำหนด
        file.save(file_path)
        
        return render_template('index.html', filename=filename)
    else:
        return redirect(request.url)

# ฟังก์ชันสำหรับลบรูปภาพ
@app.route('/delete', methods=['POST'])
def delete_file():
    filename = request.form['filename']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return render_template('index.html', filename=None)

#ฟังชันส์สำหรับลบรูปภาพในโฟลเดอร์ result หากไม่ได้ save(โฟลเดอร์จะไม่ได้มีภาพเยอะ)
@app.route('/clear_results', methods=['POST'])
def clear_results():
    try:
        # ค้นหารายการชื่อไฟล์ที่บันทึกในฐานข้อมูล
        cur = mysql.connection.cursor()
        cur.execute("SELECT name FROM images")
        saved_files = {row[0] for row in cur.fetchall()}  # แปลงเป็นเซตเพื่อให้ค้นหาเร็วขึ้น
        cur.close()

        # ค้นหาไฟล์ทั้งหมดในโฟลเดอร์ result
        files = glob.glob(os.path.join(app.config['RESULT_FOLDER'], "*"))

        cleared_files = []
        skipped_files = []

        # ตรวจสอบและลบไฟล์ที่ไม่อยู่ในฐานข้อมูล
        for file in files:
            filename = os.path.basename(file)
            if filename not in saved_files:
                os.remove(file)
                cleared_files.append(filename)
            else:
                skipped_files.append(filename)

        # ส่งผลลัพธ์กลับ
        return jsonify({
            "success": True,
            "message": f"Cleared {len(cleared_files)} files. Skipped {len(skipped_files)} files.",
            "cleared_files": cleared_files,
            "skipped_files": skipped_files
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

    
@app.route("/detect", methods=["POST"])
def detect():
    try:
        # รับไฟล์ภาพจากฟอร์ม
        if "image_file" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        buf = request.files["image_file"]

        # ตรวจจับวัตถุในภาพ
        results = detect_objects_on_image(buf)

        # สร้างชื่อไฟล์ใหม่สำหรับผลลัพธ์
        result_filename = f"result_{buf.filename}"
        result_filepath = os.path.join(app.config['RESULT_FOLDER'], result_filename)

        # บันทึกผลลัพธ์ในโฟลเดอร์ result
        results[0].save(result_filepath)

        # ส่งผลลัพธ์กลับในรูปแบบ JSON
        return jsonify({"boxes": results[1], "result_filename": result_filename})
    except Exception as e:
        # จับข้อผิดพลาดและส่งข้อความกลับ
        return jsonify({"error": str(e)}), 500

def detect_objects_on_image(buf):
    try:
        # โหลด YOLO model
        model = YOLO("weights/object_detection/best.pt")
        
        # ทำการทำนาย
        results = model.predict(Image.open(buf.stream))
        result = results[0]

        # ดึงข้อมูล bounding boxes และ class
        output = []
        for box in result.boxes:
            x1, y1, x2, y2 = [round(x) for x in box.xyxy[0].tolist()]
            class_id = int(box.cls[0].item())
            prob = round(box.conf[0].item(), 2)
            label = result.names[class_id]
            output.append([x1, y1, x2, y2, label, prob])

        return result, output
    except Exception as e:
        print(f"Error in detect_objects_on_image: {e}")
        raise
    
#ฟังชันส์สำหรับดึงข้อมูลมาแสดงในหน้า history
@app.route('/history')
def list_images():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM images ORDER BY id DESC")
    images = cur.fetchall()
    cur.close()

    # Debugging: ตรวจสอบข้อมูลที่ดึงมา
    print(images)

    return render_template('history.html', images=images)

#ฟังชันส์สำหรับดึง download button ข้อมูลมาแสดงในหน้า history
@app.route('/history_download/<int:image_id>', methods=['GET'])
def download_image(image_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name FROM images WHERE id = %s", (image_id,))
    image = cur.fetchone()
    cur.close()

    if image:
        # สร้างเส้นทางเต็มของไฟล์ในโฟลเดอร์ static
        file_path = os.path.join(app.root_path, 'static/result', image[1])

        if os.path.exists(file_path):  # ตรวจสอบว่าไฟล์มีอยู่จริง
            # ส่ง URL และชื่อไฟล์กลับไปที่ Frontend
            file_url = f"/static/result/{image[1]}"
            return jsonify({"file_url": file_url, "filename": image[1]}), 200
        else:
            return jsonify({"message": "File not found in static/result."}), 404
    else:
        return jsonify({"message": "Image ID not found in database."}), 404



#ฟังชันส์สำหรับลบข้อมูลในหน้า history
@app.route('/delete_image/<int:image_id>', methods=['DELETE'])
def delete_image(image_id):
    cur = mysql.connection.cursor()

    # ดึงชื่อไฟล์จากฐานข้อมูล
    cur.execute("SELECT path FROM images WHERE id = %s", (image_id,))
    image = cur.fetchone()

    if image:
        file_path = image[0]  # ใช้ path ที่เก็บไว้ในฐานข้อมูล
        if os.path.exists(file_path):
            os.remove(file_path)

        cur.execute("DELETE FROM images WHERE id = %s", (image_id,))
        mysql.connection.commit()
        
    cur.close()
    return jsonify({'message': 'Image deleted successfully!'}), 200



@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/about')
def about():
    return render_template('about.html')


#if __name__ =="__main__":
#    app.run(debug=True)
if __name__ == '__main__':
    # ดึงค่า PORT จาก Environment Variable (ถ้าไม่มีใช้ค่า 5000 เป็นค่าเริ่มต้น)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
