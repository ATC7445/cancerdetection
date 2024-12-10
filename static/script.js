function openModal() {
  document.getElementById("modalOverlay").style.display = "flex";
}

function closeModal() {
  document.getElementById("modalOverlay").style.display = "none";
}
function saveResult() {
  const imageName = document.getElementById("imageName").value;

  if (!imageName) {
      alert("No image selected to save.");
      return;
  }

  fetch('/save_result', {
      method: 'POST',
      headers: {
          'Content-Type': 'application/json'
      },
      body: JSON.stringify({ image_name: imageName })
  })
      .then(response => response.json())
      .then(data => {
          if (data.success) {
              showModal(data.message); // แสดงข้อความเมื่อบันทึกสำเร็จ
          } else {
              alert(data.message); // แสดงข้อความข้อผิดพลาด
          }
      })
      .catch(error => {
          console.error("Error:", error);
          alert("An error occurred while saving the result.");
      });
}

// ฟังก์ชันเพื่อแสดงรูปภาพทันทีที่เลือก
function showImagePreview(event) {
  const image = document.getElementById("preview");
  image.src = URL.createObjectURL(event.target.files[0]);
  image.style.display = "block";
}
// ฟังก์ชันเพื่อลบรูปภาพและซ่อนภาพตัวอย่าง
// ฟังก์ชันเพื่อลบรูปภาพและซ่อนภาพตัวอย่าง
function clearImage() {
  // ลบรูปภาพในช่อง preview
  const image = document.getElementById("preview");
  image.src = "";
  image.style.display = "none";

  // รีเซ็ต input file
  document.querySelector('input[type="file"]').value = "";

  // ลบรูปภาพในช่อง predict
  const predictImage = document.getElementById("canvas"); // อ้างอิงถึง img หรือ canvas ที่ใช้แสดงผล predict
  if (predictImage.tagName === "IMG") {
    predictImage.src = ""; // ลบรูปใน <img>
    predictImage.style.display = "none";
  } else if (predictImage.tagName === "CANVAS") {
    const ctx = predictImage.getContext("2d");
    ctx.clearRect(0, 0, predictImage.width, predictImage.height); // ลบรูปใน <canvas>
  }
}

window.onload = function () {
  predict(); // เรียกใช้ predict เมื่อหน้าโหลด
};
// ฟังก์ชันสำหรับเรียก API เพื่อลบไฟล์ในโฟลเดอร์ result
function clearResultsFolder() {
  fetch('/clear_results', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        console.log(data.message); // แสดงข้อความใน console
      } else {
        console.error("Error:", data.message);
      }
    })
    .catch(error => {
      console.error("Error:", error);
    });
}
// เรียกใช้เมื่ออัปโหลดรูปหรือกดปุ่ม delete
document.getElementById("clearButton").addEventListener("click", () => {
  clearImage(); // ลบรูปจาก preview และ predict
  clearResultsFolder(); // ลบไฟล์ในโฟลเดอร์ result
});

document.querySelector('input[type="file"]').addEventListener("change", () => {
  clearResultsFolder(); // ลบไฟล์ในโฟลเดอร์ result
});
// ตั้งชื่อไฟล์ทำนายให้ hidden input
function setPredictedImageName(imageName) {
  document.getElementById("imageName").value = imageName;

//predict สำหรับ object detection no.1
}
async function predict() {
  const form = document.getElementById("predict-form");
  form.addEventListener("submit", async (event) => {
      event.preventDefault(); // หยุดการส่งฟอร์มแบบปกติ

      const fileInput = document.querySelector('input[type="file"]');
      const file = fileInput.files[0];

      if (!file) {
          alert("กรุณาเลือกไฟล์ก่อนทำการทำนาย");
          return;
      }

      const formData = new FormData();
      formData.append("image_file", file);

      try {
          const response = await fetch("/detect", {
              method: "POST",
              body: formData,
          });

          if (!response.ok) {
              const error = await response.json();
              console.error("Error:", error.error);
              alert(`Error: ${error.error}`);
              return;
          }

          const result = await response.json();
          const resultFilename = result.result_filename;
          const boxes = result.boxes;
           // อัปเดตชื่อไฟล์ที่ทำนาย
          setPredictedImageName(resultFilename);
          // อัพเดตลิงก์ download ให้เป็น path ของไฟล์ผลลัพธ์
          const downloadLink = document.getElementById("download-link");
          downloadLink.href = `/static/result/${resultFilename}`;
          downloadLink.style.display = "inline";  // ทำให้ปุ่มดาวน์โหลดแสดง

          const resultImagePath = `/static/result/${resultFilename}`;
          const resultImage = new Image();
          resultImage.src = resultImagePath;

          resultImage.onload = () => {
              // เรียกใช้ฟังก์ชันเพื่อวาดกรอบและ label
              draw_image_and_boxes(resultImage, boxes);
          };
      } catch (error) {
          console.error("Error:", error);
          alert("มีข้อผิดพลาดในการเชื่อมต่อกับเซิร์ฟเวอร์");
      }
  });
}
// สำหรับวาด box ให้ object detection no.1
function draw_image_and_boxes(image, boxes) {
  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");
  const img = new Image();

  img.src = image.src; // ใช้รูปจาก preview
  img.onload = () => {
      // ตั้งค่า canvas ให้มีขนาดเท่ากับรูปภาพ
      canvas.width = img.width;
      canvas.height = img.height;

      // ล้าง canvas ก่อนวาดใหม่
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // วาดรูปภาพลงบน canvas
      ctx.drawImage(img, 0, 0);
  };
}

//หน้า history
//ปุ่ม delete
function deleteImage(imageId) {
  // ส่งคำขอ DELETE ไปที่ Flask
  fetch(`/delete_image/${imageId}`, {
    method: 'DELETE', // วิธี DELETE
  })
  .then(response => response.json())
  .then(data => {
    if (data.message) {
      alert(data.message);  // แสดงข้อความสำเร็จ
      // ลบแถวที่แสดงผลในตาราง
      const row = document.getElementById(`row-${imageId}`);
      row.remove();  // ลบแถวในตารางตาม ID
    } else {
      alert('Error deleting the image.');
    }
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error occurred while deleting the image.');
  });
}
// download หน้า history
// ฟังก์ชันการดาวน์โหลด
function downloadHistoryBtn(imageId) {
  fetch(`/history_download/${imageId}`, {
      method: 'GET',
  })
  .then(response => {
      if (response.ok) {
          return response.json(); // ดึงข้อมูล JSON จาก response
      } else {
          throw new Error("Failed to fetch download URL");
      }
  })
  .then(data => {
      if (data.file_url) {
          const downloadLink = document.createElement("a");
          downloadLink.href = data.file_url; // ใช้ URL ที่ส่งมาจาก Flask
          downloadLink.download = data.filename; // ตั้งชื่อไฟล์สำหรับดาวน์โหลด
          downloadLink.click(); // เรียกใช้การดาวน์โหลด
      } else {
          alert("No file URL found.");
      }
  })
  .catch(error => {
      console.error("Error:", error);
      alert("Error: " + error.message);
  });
}








  







