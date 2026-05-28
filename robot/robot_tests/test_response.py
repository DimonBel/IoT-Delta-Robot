from robot_controller import RobotController
import time as t


with RobotController(port="/dev/cu.usbmodem153408901") as rc:
    is_delta = rc.is_delta()
    print(f"isdelta resp: {is_delta}")
    
    pos = rc.get_position()
    print(f"pos response: {pos}")
    
    rc.send_axes_home(X=True, Y=True, Z=True, U=True, V=True, W=True)
    
    # rc.set_motion(speed=100, acceleration=500)
    t.sleep(0.5)
    
    # rc.move_to(X=-125, Y=160, Z=-900, U=45, V=45, W=0)
    
    # rc.move_to(X=0, Y=0, Z=-840)
    
    # for _ in range(10):
    #     rc.move_to(X=100, Y=100, Z=-750)
    #     rc.move_to(X=-100, Y=100, Z=-750)
    #     rc.move_to(X=100, Y=-100, Z=-750)
    #     rc.move_to(X=-100, Y=-100, Z=-750)
    
    # for _ in range(1):
    #     rc.move_to(X=250, Y=250, Z=-850)
    #     rc.move_to(X=-250, Y=250, Z=-850)
    #     rc.move_to(X=250, Y=-250, Z=-850)
    #     rc.move_to(X=-250, Y=-250, Z=-850)
        
    #     rc.move_to(X=200, Y=200, Z=-780)
    #     rc.move_to(X=-200, Y=200, Z=-780)
    #     rc.move_to(X=200, Y=-200, Z=-780)
    #     rc.move_to(X=-200, Y=-200, Z=-780)
    