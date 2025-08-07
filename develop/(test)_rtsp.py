import cv2


cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open RTSP stream.")
    exit()

while True:
    ret, frame = cap.read()

    if not ret:
        print("Error: Could not read frame from stream.")
        break
    resized_frame = cv2.resize(frame, (1280, 840))

    cv2.imshow("RTSP Stream", resized_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()