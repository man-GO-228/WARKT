import krpc
import math
import time
import json
from datetime import datetime

INTER_PRINT = 0.5
last_print_time = 0 

def prin(str):
    global last_print_time
    if vessel.met - last_print_time >= INTER_PRINT:
        last_print_time = vessel.met
        print(str)

def get_speed():
    """Получить скорость в м/с"""
    flight_info = vessel.flight(vessel.orbit.body.reference_frame)
    return flight_info.speed

def get_altitude_km():
    """Получить высоту в километрах"""
    return vessel.flight().mean_altitude / 1000

def get_apoapsis_km():
    """Получить высоту апоапсиса в километрах"""
    return vessel.orbit.apoapsis / 1000

def get_altitude():
    """Высота в метрах"""
    return vessel.flight().mean_altitude

def get_pitch():
    """Текущий тангаж в градусах"""
    return vessel.flight().pitch

def is_srb_empty():
    """Проверить, пуст ли твердотопливный ускоритель"""
    
    # Ищем все твердотопливные ускорители
    for engine in vessel.parts.engines:
        # Проверяем, является ли двигатель твердотопливным
        if 'solid' in engine.part.name.lower() or 'srb' in engine.part.name.lower():
            # Проверяем топливо
            if engine.has_fuel:
                # Получаем количество топлива
                fuel_amount = engine.part.resources.amount('SolidFuel')
                fuel_max = engine.part.resources.max('SolidFuel')
                
                # Если топлива меньше 1% - считаем пустым
                if fuel_amount < 0.01 * fuel_max:
                    return True
    
    return False

def check_engines_fuel():
    """Проверить, есть ли топливо для работающих двигателей"""
    
    engines_without_fuel = []
    
    for engine in vessel.parts.engines:
        if engine.active:
            try:
                has_fuel = engine.has_fuel
                
                if not has_fuel:
                    engines_without_fuel.append(engine.part.title)
                    
            except:
                print(f"  Не удалось проверить топливо")
    
    if engines_without_fuel:
        return True
    
    return False

def go_to_orbit_now():
    """Самый простой и надёжный выход на орбиту"""
    
    print("\n=== НАЧИНАЮ ЦИРКУЛЯРИЗАЦИЮ ===")
    
    # 1. Включаем SAS и ориентируемся на вектор скорости
    vessel.control.sas = True
    time.sleep(1)
    vessel.control.sas_mode = conn.space_center.SASMode.prograde
    print("✓ Ориентирован на вектор скорости")
    
    # 2. Ждём пока не окажемся в апоцентре
    print("Жду апоцентр...")
    
    # Ждём пока не окажемся в апоцентре (time_to_apoapsis станет маленьким)
    while vessel.orbit.time_to_apoapsis > 30:
        print(f"Время до апоцентра: {vessel.orbit.time_to_apoapsis:.0f}с")
        time.sleep(5)
    
    # Ждём ещё немного, чтобы быть точно в апоцентре
    print("Приближаюсь к точке манёвра...")
    time.sleep(vessel.orbit.time_to_apoapsis - 5)
    
    # 3. Включаем двигатель
    print("✓ Достигнут апоцентр!")
    print("Включаю двигатель...")
    vessel.control.throttle = 1.0
    
    # 4. Ускоряемся 40 секунд (примерно нужно для поднятия перицентра)
    print("Разгоняюсь 40 секунд...")
    for i in range(30):
        periapsis = vessel.orbit.periapsis
        apoapsis = vessel.orbit.apoapsis
        
        if i % 5 == 0:  # Выводим раз в 5 секунд
            print(f"{i}с: Перицентр {periapsis/1000:.1f}км, Апоцентр {apoapsis/1000:.1f}км")
            
        time.sleep(1)
    
    # 5. Выключаем
    vessel.control.throttle = 0
    print("✓ Двигатель выключен")
    
    # 6. Результаты
    print(f"\n=== ОРБИТА ДОСТИГНУТА ===")
    print(f"Перицентр: {vessel.orbit.periapsis/1000:.1f}км")
    print(f"Апоцентр: {vessel.orbit.apoapsis/1000:.1f}км")
    
    return True

def save_flight_data():
    """Сохранить собранные данные в JSON файл"""
    if flight_data:
        try:
            filename = f"flight_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='UTF-8') as f:
                json.dump(flight_data, f)
            print(f"\n✓ Данные сохранены в файл: {filename}")
            print(f"Всего записей: {len(flight_data)}")
            return True
        except Exception as e:
            print(f"Ошибка при сохранении данных: {e}")
            return False
    else:
        print("Нет данных для сохранения")
        return False

# Подключение к KSP
print("Подключаюсь к KSP...")
conn = krpc.connect(name='Автопилот: Орбита Луны')
vessel = conn.space_center.active_vessel

# Инициализация переменных для сбора данных
flight_data = []  # Будет хранить данные в формате [[time, x, y, height, speed]]
last_data_save_time = time.time()
data_collection_interval = 1.0  # секунд между записями
data_collection_active = True  # Сбор данных с самого начала
data_collection_start_time = vessel.met

# Базовые параметры
APOAPSIS_LEO = 100  # м (100 км)
PERIAPSIS_LEO = 100000  # м
APOAPSIS_TARGET = 100000  

# Запуск двигателей
print("\n=== ЗАПУСК ДВИГАТЕЛЕЙ ===")
vessel.control.throttle = 1.0
vessel.control.activate_next_stage()
vessel.control.sas = True
print("Двигатели запущены.")

state = 0
level = 0
program_running = True

print("\n=== НАЧАЛО СБОРА ДАННЫХ ===")
print("Данные сохраняются каждую секунду в формате [время, x, y, высота, скорость]")

while program_running:
    # === СБОР ДАННЫХ НА КАЖДОМ ШАГЕ ЦИКЛА ===
    current_time = time.time()
    if data_collection_active and current_time - last_data_save_time >= data_collection_interval:
        try:
            # Получаем текущие данные
            flight_time = vessel.met
            altitude = vessel.flight().mean_altitude
            speed = get_speed()
            
            # Получаем координаты (x, y)
            ref_frame = vessel.orbit.body.reference_frame
            position = vessel.position(ref_frame)
            
            # Сохраняем в формате [[time, x, y, height, speed]]
            flight_data.append([
                float(flight_time),  # время полета в секундах
                float(position[0]),  # координата X
                float(position[1]),  # координата Y
                float(altitude),     # высота в метрах
                float(speed)         # скорость в м/с
            ])
            
            last_data_save_time = current_time
            
            # Выводим информацию о сборе данных (раз в 10 секунд)
            if int(flight_time) % 10 == 0 and flight_time > 0:
                print(f"[Данные] t={flight_time:.1f}s, h={altitude/1000:.1f}km, v={speed:.1f}m/s")
                
        except Exception as e:
            print(f"Ошибка при сборе данных: {e}")
    
    # === АВТОПИЛОТ ===
    match state:
        case 0:
            prin(f"Скорость сейчас {get_speed()} м/с")
            if get_speed() >= 100:
                state = 1
                vessel.control.sas = False
                # Начинаем гравитационный поворот
                print(f"state={state}. Начинаем гравитационный разворот.")
                
        case 1:
            altitude = vessel.flight().mean_altitude
            current_pitch = vessel.flight().pitch
            
            # 1. ПЛАВНАЯ интерполяция вместо ступенек
            if altitude < 1000:
                target = 90  # Первые 1км - строго вертикально
            elif altitude < 70000:
                # Плавный переход от 90° до 5°
                progress = (altitude - 1000) / 69000  # 0 на 1км, 1 на 70км
                target = 90 - (85 * progress)  # 90° → 5°
            else:
                target = 5
            
            # 2. Адаптивный коэффициент усиления
            error = target - current_pitch
            
            # Чем больше ошибка - тем сильнее реакция, но плавнее
            if abs(error) > 30:
                Kp = 1/40.0  # Большая ошибка - плавно
            elif abs(error) > 15:
                Kp = 1/30.0  # Средняя ошибка
            else:
                Kp = 1/50.0  # Малая ошибка - очень плавно
            
            # 3. Пропорциональное управление
            control = error * Kp
                        
            # 5. Ограничение с плавным насыщением
            if control > 0.4:
                control = 0.4
            elif control < -0.4:
                control = -0.4
            
            # 6. Применяем управление
            vessel.control.pitch = control
            vessel.control.roll = 0
            
            # 7. Вывод информации
            if int(time.time()) % 2 == 0:
                prin(f"Alt: {altitude/1000:5.1f}km | "
                    f"Target: {target:4.0f}° | "
                    f"Current: {current_pitch:5.1f}° | "
                    f"Error: {error:+6.1f}° | "
                    f"Control: {control:6.3f}")
            
            # 8. Условие перехода (добавляем проверку скорости)
            speed = vessel.flight(vessel.orbit.body.reference_frame).speed
            if altitude > 71000 and speed > 1500:
                print("✓ Высота 71км достигнута, скорость достаточна")
                state = 2
                
        case 2:
            altitude = vessel.flight().mean_altitude
            current_pitch = vessel.flight().pitch
            target = 1
            
            # 2. Адаптивный коэффициент усиления
            error = target - current_pitch
            
            # Чем больше ошибка - тем сильнее реакция, но плавнее
            if abs(error) > 30:
                Kp = 1/40.0  # Большая ошибка - плавно
            elif abs(error) > 15:
                Kp = 1/30.0  # Средняя ошибка
            else:
                Kp = 1/50.0  # Малая ошибка - очень плавно
            
            # 3. Пропорциональное управление
            control = error * Kp
                        
            # 5. Ограничение с плавным насыщением
            if control > 0.4:
                control = 0.4
            elif control < -0.4:
                control = -0.4
            
            # 6. Применяем управление
            vessel.control.pitch = control
            vessel.control.roll = 0
            
            # 7. Вывод информации
            if int(time.time()) % 2 == 0:
                prin(f"Alt: {altitude/1000:5.1f}km | "
                    f"Target: {target:4.0f}° | "
                    f"Current: {current_pitch:5.1f}° | "
                    f"Error: {error:+6.1f}° | "
                    f"Control: {control:6.3f}")
            state = 3
            
        case 3:  # После гравитационного поворота
            print("Гравитационный поворот завершён!")
            vessel.control.throttle = 0
            go_to_orbit_now()
            state = 4
            
        case 4:  # Автопилот завершил работу
            print("\n=== АВТОПИЛОТ ЗАВЕРШИЛ РАБОТУ ===")
            print("Продолжаю сбор данных полета...")
            state = 5
            
        case 5: 
            data_collection_active = False
            save_flight_data()
            print("\n=== ОБРАБОТКА ДАННЫХ ===")
            print(f"Первая запись: t={flight_data[0][0]:.1f}s, h={flight_data[0][3]/1000:.1f}km")
            print(f"Последняя запись: t={flight_data[-1][0]:.1f}s, h={flight_data[-1][3]/1000:.1f}km")
            print(f"Всего точек данных: {len(flight_data)}")
            print(f"Общая продолжительность полета: {flight_data[-1][0] - flight_data[0][0]:.1f} секунд")
    
    # === ПРОВЕРКА СОСТОЯНИЯ SRB И ПЕРЕКЛЮЧЕНИЕ СТУПЕНЕЙ ===
    if is_srb_empty() and (level == 0):
        time.sleep(1)
        print("Отделяем SRB...")
        vessel.control.activate_next_stage()
        level = 1

    if (vessel.thrust == 0) and (level == 1):
        time.sleep(1)
        vessel.control.activate_next_stage()
        vessel.control.sas = True
        time.sleep(0.2)  # Ждём инициализации
        vessel.control.sas_mode = conn.space_center.SASMode.stability_assist
        level = 3

    if (vessel.thrust == 0) and (level == 2):
        time.sleep(1)
        vessel.control.activate_next_stage()
        vessel.control.sas = True
        time.sleep(0.2)  # Ждём инициализации
        vessel.control.sas_mode = conn.space_center.SASMode.stability_assist
        level = 3
