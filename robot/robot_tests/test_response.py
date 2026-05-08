from robot_controller import RobotController
import time as t

with RobotController(port="COM6") as rc:
    is_delta = rc.is_delta()
    print(f"isdelta resp: {is_delta}")
    
    pos = rc.get_position()
    print(f"pos response: {pos}")
    
    # rc.send_axes_home(X=True, Y=True, Z=True, U=True, V=True, W=True)
    
    rc.set_motion(speed=200, acceleration=1000)
    t.sleep(0.5)
    
    # rc.move_to(X=0, Y=0, Z=-850, U=0, V=0, W=70)
    rc.move_to(X=0, Y=0, Z=-780)
    
    for _ in range(5):
        rc.move_to(X=250, Y=250, Z=-850)
        rc.move_to(X=-250, Y=250, Z=-850)
        rc.move_to(X=250, Y=-250, Z=-850)
        rc.move_to(X=-250, Y=-250, Z=-850)
        
        rc.move_to(X=200, Y=200, Z=-780)
        rc.move_to(X=-200, Y=200, Z=-780)
        rc.move_to(X=200, Y=-200, Z=-780)
        rc.move_to(X=-200, Y=-200, Z=-780)
    
    