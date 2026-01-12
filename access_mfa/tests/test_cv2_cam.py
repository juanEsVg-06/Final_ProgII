import cv2

def main():
    # En Windows, CAP_DSHOW suele evitar bloqueos
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    print("isOpened:", cap.isOpened())
    if not cap.isOpened():
        print("No se pudo abrir la cámara con index=0")
        return

    while True:
        ok, frame = cap.read()
        if not ok:
            print("No se pudo leer frame (cap.read() = False)")
            break

        cv2.imshow("RAW CAM (ESC para salir)", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
